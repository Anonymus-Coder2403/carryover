# Carryover

App that turns a dying AI chat session into a transferable context capsule, then
rehydrates it into a fresh session in Claude, ChatGPT or Cursor. Also runs as an MCP
server so an assistant can save and load capsules directly.

Originally built at the Airtribe x Render Ship Room hackathon, Bengaluru, 12 Sep 2026.
Now being turned into a real portfolio project: real user accounts, Postgres instead of
SQLite, and a proper frontend, none of which the hackathon build had time for.

## Read these before touching code

All docs live at the repo root, they describe the whole monorepo.

- `SPEC.md` high level and low level design, every endpoint and function
- `BUILD_PLAN.md` the original hackathon timebox, kept as history, not a living plan
- `RESEARCH.md` competitive landscape and the research that shapes the product
- `CONSTRAINTS.md` non negotiables, and the 13 Sep 2026 incident writeup

## Layout

Monorepo, two apps, no shared tooling between them:

- `apps/api` FastAPI backend. `uv` managed. Package `app/` split by responsibility:
  `main.py` (app wiring), `config.py` (env vars), `db.py` (SQLAlchemy engine/session),
  `models.py` (the `Capsule` model), `auth.py` (Supabase JWT verification, the
  `/mcp/<token>` path middleware), `gemini.py` (all Gemini calls and prompts),
  `capsules.py` (capsule creation, rendering, search), `mcp.py` (the MCP JSON-RPC
  handlers). `index.html` is still served from this app, unauthenticated, see below.
- `apps/web` Next.js app (App Router, TypeScript, Tailwind), `npm` managed. Explains the
  product, and is the only way to get a Supabase access token: `/signup`, `/login`,
  `/account` (shows the token and a ready to paste MCP client config). `/oauth/consent`
  is the consent screen for Supabase's OAuth 2.1 Server, used when an OAuth based MCP
  client (claude.ai's website connector) asks for access, as opposed to a client that
  takes a pasted bearer token (Claude Code, Claude Desktop). Does not yet host the capsule
  creation UI, that still lives in `apps/api/app/index.html`.

## Current state

Backend was live at https://carryover-kxq7.onrender.com as a single Render web service on
SQLite. That deploy predates this restructure and needs to move to two services (the API
and the Next.js app) against a Supabase Postgres database before it matches this repo
again. Treat the live URL as stale until that redeploy happens, verify what is actually
live by checking Render, never from memory of having pushed.

MCP server at `POST /mcp`, streamable HTTP, stateless, plain JSON, two tools:
`save_capsule` and `load_capsule`. Requires a Supabase access token, either
`Authorization: Bearer <jwt>` or the same token as the last path segment, `/mcp/<jwt>`,
for clients that cannot send headers. The token is verified against `SUPABASE_URL`'s
published JWKS (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, `pyjwt[crypto]`,
`PyJWKClient`, ES256/RS256, audience not checked since OAuth issued tokens and password
flow tokens carry different `aud` claims). Supabase signs with per project asymmetric
keys now, not a shared secret, a static `SUPABASE_JWT_SECRET`/HS256 check fails on every
token for a project on the current signing scheme, confirmed against a real token this way
(`ES256` in the header, verification failed until `verify_jwt` switched to JWKS and
`pyjwt` got installed with the `crypto` extra so it could actually do ES256 signature
checks). The JWT's `sub` claim is the owner, each Supabase user has their own private
capsules.

Two ways to get that token to the MCP server. Claude Code and Claude Desktop take a pasted
bearer token or header, copied from `/account`, nothing else needed. claude.ai's website
custom connectors are OAuth only, no pasted token option, so `/mcp`'s 401 response points
at `GET /.well-known/oauth-protected-resource` (RFC 9728), which names Supabase's own
project as the authorization server. Supabase's OAuth 2.1 Server feature (beta, on by
project setting) handles the authorization code and PKCE exchange and dynamic client
registration, `apps/web`'s `/oauth/consent` page is the one piece we build, the actual
consent screen. The access token it issues is the same kind of Supabase JWT either way,
verified the same way by `auth.py`.

Web routes (`/`, `/api/capsule`, `/api/resume/{id}`, `/api/verify/{cid}`, `/api/search`,
`/c/{id}`) stay unauthenticated by explicit decision, `owner` is `NULL` for anything made
there, exactly as before. This reproduces the same ownerless row shape as the 13 Sep 2026
incident in `CONSTRAINTS.md`, accepted for now since porting the capsule tool behind login
in the Next.js app is future work, not done yet.

Shipped and verified (backend, against a local Postgres/SQLite smoke test, not yet
redeployed): capsule extraction, multi target rehydration, the token meter and health
verdict (P1), the fidelity check (P2), a length based model router, a client side file
parser for ChatGPT and Claude exports, cosine search over saved capsules using Gemini
embeddings, a verbatim literals list with a regex URL backstop, capsule chaining through
an optional parent id, and Supabase JWT auth on the MCP path replacing the old shared
`MCP_TOKENS` bearer scheme.

Models are env vars. `GEMINI_MODEL` (default gemini-3.6-flash) handles extraction and the
fidelity check. `GEMINI_LITE` (default gemini-3.1-flash-lite) is used only for transcripts
at or below `ROUTE_AT` characters, and `ROUTE_AT` defaults to 0 because the lite model
drops long URLs from the `literals` field and fails JSON mode about a third of the time on
them. Turn it on only with a measurement that says literals survive. `GEMINI_EMBED` (default
gemini-embedding-001) embeds capsules. gemini-2.5-flash is retired for new keys and
gemini-3.5-flash-lite returned malformed JSON in testing, do not use either.

## Env vars

`apps/api`: `DATABASE_URL` (Supabase Postgres connection string), `SUPABASE_URL` (the
project URL, used to fetch its JWKS for MCP token verification and to name the
authorization server in the protected resource metadata), `PUBLIC_API_URL` (this API's own
public base URL, used in the same metadata and in the `WWW-Authenticate` header),
`GEMINI_API_KEY`, `GEMINI_MODEL`,
`GEMINI_LITE`, `ROUTE_AT`, `GEMINI_EMBED`. See `apps/api/.env.example`.

`apps/web`: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
`NEXT_PUBLIC_API_URL` (the `apps/api` deploy this frontend points at). See
`apps/web/.env.example`.

## Hard rules for this repo

- Two deploys, one per app: `apps/api` (FastAPI) and `apps/web` (Next.js). They don't
  share build tooling, but the JWT verification secret and Supabase project must match on
  both sides or logins from the web app won't authenticate against the API.
- `apps/api` is `uv` only. `uv lock` after any pin change, `uv run --frozen` locally.
  Never pip, never `uv pip`. `requirements.txt` is kept in sync via
  `uv export --frozen --no-hashes --no-dev -o requirements.txt`, it is not hand edited.
- `apps/web` is `npm` only, standard Next.js conventions (App Router, `next build`/
  `next lint` must pass before anything ships).
- Gemini calls in `apps/api` stay on stdlib `urllib`, no Google SDK, so there is no SDK
  version risk on that path specifically. New dependencies elsewhere (SQLAlchemy, `psycopg`,
  `pyjwt[crypto]` on the backend; `@supabase/supabase-js`, `@supabase/ssr` on the frontend) are fine,
  the hackathon's zero dependency cap no longer applies.
- MCP requires a verified Supabase JWT, no exceptions, no fallback to a shared secret.
- Supabase's OAuth Server has dynamic client registration on, by deliberate choice, so
  claude.ai's connector can register itself without us hardcoding its redirect URI. That
  means any OAuth client can self register and ask a user to approve access under a self
  declared name. The `/oauth/consent` screen showing that name and the requested scopes
  before approval is the only defense, don't weaken or skip that screen to streamline the
  flow.
- The web capsule tool (`index.html` and its `/api/*` routes) has no login wall, by
  explicit decision, see Current state above. If that changes, update this file and
  `CONSTRAINTS.md` together, don't let one drift from the other.
- No browser storage APIs for capsule state on the web tool, server side only. The Next.js
  app's Supabase session cookies are the one exception, that's how Supabase Auth works.
- Cosine search stays pure Python, no numpy, no vector extension, until a measurement says
  otherwise.
- Never invent a metric. Every number shown in the UI is computed at runtime from real
  input.

## Style

- No em dashes. No hyphenated compound words, write "multi target" not "multi-target".
- Sentence case headings.
- Short human style variable names, no comments unless asked.
