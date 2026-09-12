# Carryover spec

## The product in one line

Your AI gets measurably worse before it runs out of room. Carryover tells you when to
move, and moves the thinking for you.

## End to end flow

```
user pastes dying chat
        |
        v
[client] token estimate, health verdict          <- instant, no network
        |
        v
POST /api/capsule  ---> Gemini 2.5 Flash, JSON mode
        |                 extract ContextCapsule
        v
   SQLite row (id, capsule json, source token count)
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

Single process. No queue, no worker, no cache, no vector store. Every stage is either
one model call or pure arithmetic.

## High level design

Three layers, all in `main.py`.

**Ingestion.** Accepts raw pasted transcript text. No parsers for `conversations.json`,
no file upload, no browser extension. Paste is the only path in v1 because it works
identically for ChatGPT, Claude, Gemini and any other assistant, and because a judge can
do it in five seconds.

**Compression.** One Gemini call with `responseMimeType: application/json` produces a
`ContextCapsule`. The capsule is the product. It is deliberately lossy about prose and
deliberately lossless about decisions, rejected approaches and constraints, because those
are the expensive things to rediscover.

**Rehydration.** Pure python string assembly. Three dialects from one capsule. No model
call, so target switching and budget switching are instant in the UI.

**Verification.** A second model call that treats the capsule as the only source and
answers questions drawn from the original transcript. This is the differentiator. It
turns "trust us, the handoff worked" into a number on screen.

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
  "glossary":     [{"term": "", "means": ""}]
}
```

Field order is also priority order for budget truncation. `goal`, `state` and
`next_action` never get cut.

### SQLite

```sql
create table if not exists caps (
  id       text primary key,
  data     text not null,      -- capsule json
  src_toks integer default 0,  -- estimated tokens of the source transcript
  created  text default current_timestamp
);
```

Path `/tmp/carryover.db` by default, overridden on Render with `DB_PATH=/var/data/carryover.db`
on a 1 GB persistent disk. Capsules survive deploys. The `emb` column is added by a pragma
check in `db()` so old rows are not a migration problem.

## Low level design

### Existing, do not rewrite

| Function | Behaviour |
|---|---|
| `db()` | opens sqlite, creates table, returns connection |
| `gemini(prompt)` | POSTs to `generativelanguage.googleapis.com`, JSON mode, temp 0.2, strips code fences, returns dict. Raises 502 with the upstream body on failure |
| `blank(c)` | fills missing capsule keys so renderers never KeyError |
| `render(c, target, budget)` | assembles the resume prompt. Claude gets XML tags, ChatGPT gets markdown headers, Cursor gets rules file comments |
| `POST /api/capsule` | validates length, calls gemini, stores, returns `{id, capsule}` |
| `GET /api/capsule/{id}` | returns stored capsule |
| `GET /api/resume/{id}` | plain text resume prompt, query params `target`, `budget` |
| `GET /healthz` | `{ok, key}` where `key` reports whether GEMINI_API_KEY is set. Proves presence, not that the model accepts it. Only a real `POST /api/capsule` proves the core action |
| `POST /api/verify/{id}` | body `{transcript}`, one model call, returns `{checks, verdict, passed, total}`. Transcript is not stored |
| `GET /api/search` | query `q`, embeds it, cosine scan over stored capsules, top five |
| `POST /mcp` | MCP streamable HTTP, protocol 2025-11-25, stateless JSON. 401 with `WWW-Authenticate: Bearer` unless the bearer token matches an entry in `MCP_TOKENS`. Handles `initialize`, `ping`, `tools/list`, `tools/call`, 202 for notifications, JSON-RPC error for anything else. `GET /mcp` is 405 |
| `owner_of(req)` | constant time match of the bearer token, or the token from a `/mcp/<token>` path, against `MCP_TOKENS`, returns a 12 character hash as the owner id, or None |
| `PathToken` middleware | rewrites `/mcp/<token>` to `/mcp` before routing and before uvicorn logs the path, stashing the token in the ASGI scope. Exists for clients that cannot send headers, ChatGPT custom connectors offer only OAuth or nothing. Verified that the token never appears in the access log |
| `make_capsule(t, owner)`, `search_caps(q, owner)` | the internals. The `/api/capsule` and `/api/search` routes call them with no owner, so the web can only make and see public capsules. `load(cid, owner)` returns 404 for a capsule whose owner does not match |
| `tool(name, args, base)` | `save_capsule(transcript)` returns id, share link, model and capsule. `load_capsule(id or query, target)` returns the resume prompt or search hits |
| `route(text)` | picks the lite or full model by transcript length |
| `make_capsule(t, owner, parent)` | extraction, with the parent capsule appended as prior context when given |
| `embed(text)`, `cosine(a, b)` | Gemini embedding via urllib, pure Python cosine |
| `GET /` and `GET /c/{id}` | serve `index.html`, the second substitutes `__PRELOAD__` |

### P1, built: token meter and compression ratio

Client side only, in `index.html`. No server involvement, so it renders the instant the
judge stops typing.

```js
function toks(s){ return Math.ceil(s.length / 4); }

function health(t, win){
  const pct = t / win;
  if (pct < 0.40) return {label: "Healthy", note: "Plenty of room. Keep going."};
  if (pct < 0.60) return {label: "Degrading", note: "Quality drops in this band. Good time to move."};
  return {label: "Hand off now", note: "Past the point where models reliably hold the thread."};
}
```

Wire `oninput` on the textarea, debounced 150ms, to update a meter above the button.
`win` defaults to 200000 with a small select for 128k / 200k / 1M.

The 40% and 60% thresholds come from RESEARCH.md and are honest estimates, not measured
values. Label them in the UI as "estimated" so no fabricated precision is implied.

After a capsule is made, show compression as `srcToks` to `toks(prompt)`, rendered as
"Carried N tokens of thinking in M" plus the ratio. Both numbers are real.

### P1, not built: server side source token count

The ratio is computed client side from the pasted text and the rendered prompt. A shared
`/c/{id}` link therefore shows the prompt but not the ratio. Add `src_toks` to the row if
that matters.

### P2, built: fidelity check

New endpoint. One model call. Returns immediately renderable JSON.

```
POST /api/verify/{cid}
body: {"transcript": "..."}    the client still holds it, do not store it server side
```

Prompt shape:

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

Response handling: score is `sum(preserved) / len(checks)`. Render each check as a row
with the question, the capsule's answer, and a pass or fail mark. Show the score as
"3 of 3 preserved".

Do not store transcripts. The privacy line in the demo is "your conversation is never
written to our database, only the capsule is", and it must be literally true.

### P3, partly built

Copy button feedback and focus states shipped. Mobile stacking exists via the single
column grid under 820px but was not checked on a phone. The budget selector for the
window size was cut, the window is hardcoded to 200k.

### Built beyond the plan, same day

**Model router.** `route(text)` in `main.py` picks `GEMINI_LITE` for transcripts at or
below `ROUTE_AT` characters and `GEMINI_MODEL` above it. Default is off, `ROUTE_AT=0`. The fidelity check always uses
`GEMINI_MODEL` so the judge is never weaker than the compressor. The response to
`POST /api/capsule` includes `model` so the UI reports which one ran. Measured on a 14k
character transcript, three runs each: 3.6-flash 10.6 to 13.2s, 3.1-flash-lite 2.6 to 3.1s
with equal or fuller capsules. That held until the `literals` field was added: the lite model
then dropped every long URL in five of five runs and returned malformed JSON in two of six
calls, while the full model kept all 23 literals in three of three at about 11s. Exact values
are the point of the product, so the router defaults to off.

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
page shows a "Chain from current capsule" box once a capsule is loaded. Measured on the
sample chat plus a follow up: the child kept both rejections and both constraints from the
parent and added the new decisions.

**Export file parser.** Client side only, `conversations` and `flatten` in `index.html`.
Accepts a `.txt`, `.md` or `.json` file. Understands a full ChatGPT `conversations.json`
(array of conversations, each a `mapping` tree ordered by `create_time`), a full Claude
export (array with `name` and `chat_messages`), a flat `messages` array, or a single role
and content object. Anything else is plain text. With more than one conversation a select
appears, newest first with an estimated token count per entry, and the newest is loaded by
default. Text over 120,000 characters keeps the last 120,000, the oldest part is dropped,
and the note says so, because the recent end is what a resume needs. Unit checked in node
against synthetic ChatGPT, Claude and messages exports.

**Capsule search.** `POST /api/capsule` embeds the capsule JSON with `GEMINI_EMBED` and
stores the vector in an `emb` column added by a pragma check in `db()`. `GET
/api/search?q=` embeds the query and does a linear cosine scan in pure Python over every
row, returning the top five as `{id, title, goal, score}`. Embedding failure is
non fatal, the capsule is stored with a null vector and skipped by search.

## Deliberately out of scope

Browser extension. Accounts and auth. Capsule chaining across sessions. Team sharing.
Postgres. Anything with a queue. The MCP server, export parsing and capsule search were
out of scope for the demo and shipped the same afternoon once the demo build was frozen.

Reasons are in RESEARCH.md. The short version: MCP cannot be judged in a browser, and the
rubric awards 20 points for a judge opening a Render URL and using the product directly.

## Environment

| Var | Required | Default |
|---|---|---|
| `GEMINI_API_KEY` | yes | none, `/healthz` reports false |
| `GEMINI_MODEL` | no | `gemini-3.6-flash`, used above `ROUTE_AT` and for the fidelity check |
| `GEMINI_LITE` | no | `gemini-3.1-flash-lite`, used at or below `ROUTE_AT` |
| `ROUTE_AT` | no | `0`, which sends everything to `GEMINI_MODEL`. Set to a character count to route shorter transcripts to `GEMINI_LITE` |
| `GEMINI_EMBED` | no | `gemini-embedding-001` |
| `MCP_TOKENS` | for MCP | none. Comma separated bearer tokens, one per user. With none set every MCP call is 401 |
| `DB_PATH` | no | `/tmp/carryover.db` |
| `PORT` | set by Render | 10000 |

Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
