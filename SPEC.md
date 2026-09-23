# Carryover spec

## The product in one line

Your AI gets measurably worse before it runs out of room. Carryover tells you when to
move, and moves the thinking for you.

## Layout

Monorepo. `apps/api` is the FastAPI backend this spec mostly describes. `apps/web` is a
Next.js app that explains the product and is where a user signs up, logs in, and gets the
Supabase access token needed to call the MCP server. See `AGENTS.md` for the file by file
breakdown of both.

## End to end flow, apps/api

```
user pastes dying chat
        |
        v
[client] token estimate, health verdict          <- instant, no network
        |
        v
POST /api/capsule  ---> Gemini, JSON mode
        |                 extract ContextCapsule
        v
   Postgres row (id, capsule json, owner, parent, embedding)
        |
        +--> GET /api/resume/{id}?target=&budget=   pure python, no model call
        |         renders Claude / ChatGPT / Cursor dialect
        |
        +--> POST /api/verify/{id}                  one model call
                  answers 3 questions from capsule only, scores fidelity
        |
        v
user copies resume prompt into a fresh session in any assistant
```

Single process for the API. No queue, no worker, no cache, no vector store. Every stage is
either one model call or pure arithmetic. The MCP path (`POST /mcp`) runs the same
`make_capsule`/`load`/`search_caps` functions, the only difference from the web path is
that it has a verified owner.

## High level design

Split across `apps/api/app/*.py` by responsibility, see `AGENTS.md` for the module list.

**Ingestion.** Accepts raw pasted transcript text. No parsers for `conversations.json`
server side, no browser extension. The client side file parser (see below) turns exports
into the same pasted text shape before it ever reaches the server, so the API only ever
sees plain text.

**Compression.** One Gemini call with `responseMimeType: application/json` produces a
`ContextCapsule`. The capsule is the product. It is deliberately lossy about prose and
deliberately lossless about decisions, rejected approaches and constraints, because those
are the expensive things to rediscover.

**Rehydration.** Pure python string assembly. Three dialects from one capsule. No model
call, so target switching and budget switching are instant in the UI.

**Verification.** A second model call that treats the capsule as the only source and
answers questions drawn from the original transcript. This is the differentiator. It
turns "trust us, the handoff worked" into a number on screen.

**Auth.** Supabase Auth issues JWTs to users of the Next.js app. `apps/api` verifies them
itself against `SUPABASE_URL`'s published JWKS (ES256), it never calls Supabase's auth API
to check a token. This gates the MCP path only, the web path stays open, see
`CONSTRAINTS.md`.

## Data model

### ContextCapsule

```json
{
  "title": "short name for this work",
  "goal": "one sentence",
  "state": "where the work stands now",
  "decisions":    [{"choice": "", "why": ""}],
  "rejected":     [{"approach": "", "why_failed": ""}],
  "constraints":  ["hard rules the user set"],
  "artifacts":    [{"name": "", "kind": "", "where": ""}],
  "open_threads": ["unresolved questions"],
  "next_action":  "the single next step",
  "literals":     ["every exact URL, id, file path, command, env var name, model name or config string, verbatim"],
  "glossary":     [{"term": "", "means": ""}]
}
```

Field order is also priority order for budget truncation. `goal`, `state` and
`next_action` never get cut.

### Postgres

SQLAlchemy model `Capsule` in `apps/api/app/models.py`:

```python
class Capsule(Base):
    __tablename__ = "capsules"
    id      = Column(String, primary_key=True)
    data    = Column(JSON, nullable=False)   # capsule json
    emb     = Column(JSON, nullable=True)    # embedding vector, json array of floats
    owner   = Column(String, nullable=True, index=True)  # Supabase user id, or NULL for web capsules
    parent  = Column(String, nullable=True)
    created = Column(DateTime(timezone=True), server_default=func.now())
```

`DATABASE_URL` is Supabase's Postgres connection string. `Base.metadata.create_all()` runs
on startup, there is no migration tool yet, this is a single table with no evolving shape
so it has not been needed. No `src_toks` column, the token ratio shown in the UI is
computed client side and not persisted, see P1 below.

## Low level design

### Existing, do not rewrite

| Function | Module | Behaviour |
|---|---|---|
| `init_db()` | `db.py` | creates the Postgres engine and the `capsules` table if missing |
| `gemini(prompt)` | `gemini.py` | POSTs to `generativelanguage.googleapis.com`, JSON mode, strips code fences, returns dict. Raises 502 with the upstream body on failure |
| `blank(c)` | `capsules.py` | fills missing capsule keys so renderers never KeyError |
| `render(c, target, budget)` | `capsules.py` | assembles the resume prompt. Claude gets XML tags, ChatGPT gets markdown headers, Cursor gets rules file comments |
| `POST /api/capsule` | `routes.py` | validates length, calls `make_capsule` with no owner, returns `{id, capsule}` |
| `GET /api/capsule/{id}` | `routes.py` | returns stored capsule and its parent id |
| `GET /api/resume/{id}` | `routes.py` | plain text resume prompt, query params `target`, `budget` |
| `GET /healthz` | `routes.py` | `{ok, key}` where `key` reports whether GEMINI_API_KEY is set. Proves presence, not that the model accepts it. Only a real `POST /api/capsule` proves the core action |
| `POST /api/verify/{id}` | `routes.py` | body `{transcript}`, one model call, returns `{checks, verdict, passed, total}`. Transcript is not stored |
| `GET /api/search` | `routes.py` | query `q`, embeds it, cosine scan over stored capsules with `owner IS NULL`, top five |
| `GET /.well-known/oauth-protected-resource` | `routes.py` | RFC 9728 protected resource metadata, `{resource, authorization_servers}`, names Supabase's project as the authorization server for `/mcp` |
| `POST /mcp` | `mcp.py` | MCP streamable HTTP, protocol 2025-11-25, stateless JSON. 401 with `WWW-Authenticate: Bearer resource_metadata="..."` (pointing at the well known URL above) unless the bearer resolves to a Supabase user id. Handles `initialize`, `ping`, `tools/list`, `tools/call`, 202 for notifications, JSON-RPC error for anything else. `GET /mcp` is 405 |
| `owner_of(req)` | `auth.py` | reads the bearer token or the `/mcp/<token>` path token, verifies it as a Supabase JWT against `SUPABASE_URL`'s JWKS, returns the `sub` claim as the owner id, or `None` |
| `verify_jwt(token)` | `auth.py` | fetches the signing key for the token's `kid` via `PyJWKClient` (cached), `jwt.decode` with `algorithms=["ES256", "RS256"]`, signature and expiry checked, audience not checked since OAuth issued tokens carry a different `aud` than password flow ones |
| `PathToken` middleware | `auth.py` | rewrites `/mcp/<token>` to `/mcp` before routing and before uvicorn logs the path, stashing the token in the ASGI scope. Exists for clients that cannot send headers |
| `make_capsule(t, owner, parent)`, `search_caps(q, owner)` | `capsules.py` | the internals. The `/api/capsule` and `/api/search` routes call them with `owner=None`, so the web can only make and see public capsules. `load(cid, owner)` raises 404 for a capsule whose owner does not match |
| `tool(name, args, owner)` | `mcp.py` | `save_capsule(transcript)` returns id, model and capsule. `load_capsule(id or query, target)` returns the resume prompt or search hits |
| `route(text)` | `gemini.py` | picks the lite or full model by transcript length |
| `embed(text)`, `cosine(a, b)` | `capsules.py` (`cosine`) and `gemini.py` (`embed`) | Gemini embedding via urllib, pure Python cosine |
| `GET /` and `GET /c/{id}` | `routes.py` | serve `index.html`, the second substitutes `__PRELOAD__` |

### P1, built: token meter and compression ratio

Client side only, in `apps/api/app/index.html`. No server involvement, so it renders the
instant the user stops typing.

```js
function toks(s){ return Math.ceil(s.length / 4); }

function health(t, win){
  const pct = t / win;
  if (pct < 0.40) return {label: "Healthy", note: "Plenty of room. Keep going."};
  if (pct < 0.60) return {label: "Degrading", note: "Quality drops in this band. Good time to move."};
  return {label: "Hand off now", note: "Past the point where models reliably hold the thread."};
}
```

Wired `oninput` on the textarea, debounced 150ms, to update a meter above the button.
`win` defaults to 200000 with a small select for 128k / 200k / 1M.

The 40% and 60% thresholds come from `RESEARCH.md` and are honest estimates, not measured
values. Labelled in the UI as "estimated" so no fabricated precision is implied.

After a capsule is made, compression shows as `srcToks` to `toks(prompt)`, rendered as
"Carried N tokens of thinking in M" plus the ratio. Both numbers are real.

### P1, not built: server side source token count

The ratio is computed client side from the pasted text and the rendered prompt. A shared
`/c/{id}` link therefore shows the prompt but not the ratio. Would need a `src_toks` column
on `Capsule` if that starts to matter.

### P2, built: fidelity check

`POST /api/verify/{cid}`. One model call. Returns immediately renderable JSON.

```
body: {"transcript": "..."}    the client still holds it, do not store it server side
```

Prompt shape (`VERIFY` in `gemini.py`):

```
You are testing whether a compressed context capsule preserved what mattered.

Write three questions that the ORIGINAL transcript answers and that a person resuming
this work would need to know. Prefer questions about decisions, ruled out approaches and
constraints over questions about facts that are easy to look up.

Then answer each question using ONLY the capsule. If the capsule does not contain the
answer, say so plainly and mark it not preserved.

Return only JSON:
{"checks":[{"q":"","a":"","preserved":true}],"verdict":"one line"}

TRANSCRIPT:
...
CAPSULE:
...
```

Response handling: score is `sum(preserved) / len(checks)`. Rendered as a row per check
with the question, the capsule's answer, and a pass or fail mark, plus "N of N preserved".

Transcripts are not stored. The privacy line is "your conversation is never written to our
database, only the capsule is", and it must be literally true, it is checked by reading
`capsules.py` and `routes.py` for any write of the raw transcript.

### P3, partly built

Copy button feedback and focus states shipped in `index.html`. Mobile stacking exists via
the single column grid under 820px but was not checked on a phone. The budget selector for
the window size was cut, the window is hardcoded to 200k.

### Built beyond the original hackathon plan

**Model router.** `route(text)` in `gemini.py` picks `GEMINI_LITE` for transcripts at or
below `ROUTE_AT` characters and `GEMINI_MODEL` above it. Default is off, `ROUTE_AT=0`. The
fidelity check always uses `GEMINI_MODEL` so the check is never weaker than the compressor.
The response to `POST /api/capsule` includes `model` so the UI reports which one ran.
Measured on a 14k character transcript, three runs each: 3.6-flash 10.6 to 13.2s,
3.1-flash-lite 2.6 to 3.1s with equal or fuller capsules. That held until the `literals`
field was added: the lite model then dropped every long URL in five of five runs and
returned malformed JSON in two of six calls, while the full model kept all 23 literals in
three of three at about 11s. Exact values are the point of the product, so the router
defaults to off.

**Literals.** The capsule has a `literals` list for every exact URL, id, file path, command,
env var name, model name and config string, verbatim. It exists because a resumed session
asked for "the provided URLs" that the capsule had paraphrased away. It renders as its own
block in every dialect and is cut only at the short budget. After extraction a regex adds
every `http(s)://` URL from the transcript that the model left out, capped at 40 entries,
because models copy long encoded URLs unreliably and a regex does not.

**Capsule chaining.** `POST /api/capsule` and the MCP `save_capsule` tool accept an
optional `parent` capsule id. The parent is loaded with the caller's ownership, so a bad,
private or foreign id is a 404 before any model call. The extraction prompt then receives
the parent capsule as prior context with the instruction to carry every decision, ruled
out approach, constraint and literal forward unless the new transcript reverses it, so the
child stands alone. The row stores `parent`, `GET /api/capsule/{id}` returns it, and the
page shows a "Chain from current capsule" box once a capsule is loaded.

**Export file parser.** Client side only, `conversations` and `flatten` in `index.html`.
Accepts a `.txt`, `.md` or `.json` file. Understands a full ChatGPT `conversations.json`
(array of conversations, each a `mapping` tree ordered by `create_time`), a full Claude
export (array with `name` and `chat_messages`), a flat `messages` array, or a single role
and content object. Anything else is plain text. With more than one conversation a select
appears, newest first with an estimated token count per entry, and the newest is loaded by
default. Text over 120,000 characters keeps the last 120,000, the oldest part is dropped,
and the note says so, because the recent end is what a resume needs.

**Capsule search.** `POST /api/capsule` embeds the capsule JSON with `GEMINI_EMBED` and
stores the vector in the `emb` column. `GET /api/search?q=` embeds the query and does a
linear cosine scan in pure Python over the caller's rows, returning the top five as
`{id, title, goal, score}`. Embedding failure is non fatal, the capsule is stored with a
null vector and skipped by search.

**Supabase Auth on MCP.** `POST /mcp` requires a Supabase access token as
`Authorization: Bearer <jwt>` or `/mcp/<jwt>`. Verified with `pyjwt[crypto]` against
`SUPABASE_URL`'s JWKS (`PyJWKClient`, cached), not a shared secret, Supabase signs with
per project asymmetric keys. Owner is the JWT `sub` claim. Replaced the earlier
`MCP_TOKENS` shared secret scheme entirely, see `CONSTRAINTS.md`.

**OAuth discovery for claude.ai's connector.** Claude Code and Claude Desktop take a
pasted bearer token, but claude.ai's website custom connectors are OAuth only. `GET
/.well-known/oauth-protected-resource` and the `resource_metadata` hint on `/mcp`'s 401
point an OAuth capable MCP client at Supabase's own OAuth 2.1 Server, which handles
authorization code plus PKCE and dynamic client registration. `apps/web`'s
`/oauth/consent` is the consent screen Supabase redirects to, the one piece of that flow
we build ourselves. The token it ends up issuing is the same kind of Supabase JWT, `/mcp`
does not know or care which path a token came from.

## apps/web

Next.js App Router, TypeScript, Tailwind. Talks to Supabase directly with
`@supabase/supabase-js` and `@supabase/ssr`, never proxies through `apps/api`.

| Route | Behaviour |
|---|---|
| `/` | landing page, explains the product, links to signup and login |
| `/signup` | server component, redirects to `/account` if already signed in, otherwise renders `signup-form.tsx` (email and password against `supabase.auth.signUp`) |
| `/login` | server component, redirects to `?next=` or `/account` if already signed in, otherwise renders `login-form.tsx` (email and password against `supabase.auth.signInWithPassword`, honors `?next=` to return to a pending OAuth consent request after logging in) |
| `/account` | server component, redirects to `/login` if there is no session, otherwise shows the current access token and a ready to paste MCP client config pointed at `NEXT_PUBLIC_API_URL` |
| `/oauth/consent` | server component, the consent screen for Supabase's OAuth 2.1 Server. Redirects to `/login?next=...` if there is no session, otherwise reads `authorization_id` from the query string, calls `supabase.auth.oauth.getAuthorizationDetails`, shows the requesting client's name and scopes, and hands off to `consent-actions.tsx` for the Approve/Deny buttons (`approveAuthorization`/`denyAuthorization`, `skipBrowserRedirect: true`, then a manual redirect to the returned `redirect_url`) |

`proxy.ts` (the Next.js 16 proxy file, formerly `middleware.ts`) refreshes the Supabase
session cookie on every request via `lib/supabase/middleware.ts`. Does not yet host the
capsule creation UI, transcript paste and rehydration still live only in
`apps/api/app/index.html`.

## Deliberately out of scope

Browser extension. Team sharing. Anything with a queue. A login wall on the web capsule
tool. Long lived or refreshable MCP tokens. Porting the capsule creation UI into
`apps/web`. Reasons for the ones that are product decisions rather than time constraints
are in `RESEARCH.md` and `CONSTRAINTS.md`.

## Environment

`apps/api`:

| Var | Required | Default |
|---|---|---|
| `DATABASE_URL` | yes | none, startup fails without it |
| `SUPABASE_URL` | yes | none, used to fetch JWKS for MCP token verification and in the protected resource metadata's `authorization_servers` |
| `PUBLIC_API_URL` | yes | none, used as `resource` in the metadata and in the 401 `WWW-Authenticate` header |
| `GEMINI_API_KEY` | yes | none, `/healthz` reports false |
| `GEMINI_MODEL` | no | `gemini-3.6-flash`, used above `ROUTE_AT` and for the fidelity check |
| `GEMINI_LITE` | no | `gemini-3.1-flash-lite`, used at or below `ROUTE_AT` |
| `ROUTE_AT` | no | `0`, which sends everything to `GEMINI_MODEL`. Set to a character count to route shorter transcripts to `GEMINI_LITE` |
| `GEMINI_EMBED` | no | `gemini-embedding-001` |
| `PORT` | set by the platform | 10000 |

Start command: `uv run --frozen uvicorn app.main:app --host 0.0.0.0 --port $PORT`

`apps/web`:

| Var | Required | Default |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | yes | none |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | yes | none |
| `NEXT_PUBLIC_API_URL` | no | `https://carryover-kxq7.onrender.com`, the `apps/api` deploy the account page points MCP clients at |

Build: `npm install && npm run build`. Start: `npm run start`.
