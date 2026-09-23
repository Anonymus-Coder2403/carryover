# Non negotiables

## From the hackathon rubric (history, no longer governs this repo)
- Live at a Render URL by 13:45. Localhost scores zero on 20 points.
- No login wall. A judge opens it and uses it directly, no account, no API key.
- One core action must work end to end on real input.
- The user leaves with something done. Here that is a copied resume prompt that works.
- Nothing pre built. Everything in this repo ships today.

The hackathon ended 12 Sep 2026. This repo is now a portfolio project, the rubric above
described that one demo, not what this app has to be going forward. The engineering rules
below are current.

## Engineering
- Monorepo, two deploys: `apps/api` (FastAPI) and `apps/web` (Next.js). Each has its own
  packaging (`uv` for the API, `npm` for the web app), no shared tooling.
- Model and embedding calls in `apps/api` use stdlib `urllib`, not a Google SDK, so there is
  no SDK version risk on that specific path. Elsewhere, dependencies are not capped, add
  what the task needs (SQLAlchemy, `psycopg`, `pyjwt` on the backend, `@supabase/supabase-js`,
  `@supabase/ssr` on the frontend).
- `apps/api` is `uv` only for packaging, locally and on its Render service. Never pip.
- Model names live in env vars, never in code. Test a model name with a real POST before
  it goes into the deploy's env panel, the model list is per key and names get retired.
- No browser storage APIs for capsule state on the web tool. The Next.js app's Supabase
  session cookies are the one exception, that is how Supabase Auth works.
- Database is Postgres on Supabase, accessed through SQLAlchemy, not SQLite. `DATABASE_URL`
  points at Supabase's connection string. `DB_PATH` and the Render persistent disk it used
  to point at are gone.
- Incident, 13 Sep 2026. Six capsules made on the website held a third party's email and
  phone and were discoverable through the public search endpoint and readable through the
  public resume endpoint without any token. All ownerless rows were deleted after a backup,
  and the deletion was verified from outside. The root cause is a design gap, not a bug:
  website capsules have no owner, and search runs over every ownerless row. The MCP path is
  unaffected because every capsule it saves has an owner.
  Same gap, current status: the web path (`index.html`, `/api/*`) was deliberately kept
  unauthenticated when Supabase Auth was added, so this shape still exists by explicit
  decision, not oversight, see `AGENTS.md`. Do not put personal data through the website
  until that path is either gated or its search/resume endpoints are scoped some other way.
- The MCP endpoint requires a Supabase access token, verified against `SUPABASE_URL`'s
  published JWKS, not a shared secret. A prior version checked a static
  `SUPABASE_JWT_SECRET` with HS256, that fails outright on any project using Supabase's
  current per project asymmetric signing keys (ES256), which this project uses, confirmed
  against a real token, do not reintroduce the static secret path. The old `MCP_TOKENS`
  shared secret scheme from before Supabase Auth existed is also gone, there is
  no fallback to it. Capsules saved through MCP are owned by the Supabase user id (`sub`
  claim), are invisible to the website and to every other user, and get no share link.
  Capsules made on the website stay public by link, unchanged. Clients that cannot send
  headers use `/mcp/<jwt>` instead, the middleware masks that path in uvicorn's access log.
  Whether a deploy's proxy logs the raw path upstream of the app is unverified per
  environment. Treat that URL as a secret regardless, it carries the token.
- Access tokens expire (Supabase default around an hour). There is no refresh flow wired
  into MCP clients yet, a user logs in again on `/account` to get a fresh token. Don't claim
  long lived MCP sessions until that is actually built.
- claude.ai's website connector cannot use a pasted bearer token, it is OAuth only, so
  `/mcp` also speaks OAuth discovery (`GET /.well-known/oauth-protected-resource`, RFC
  9728) pointing at Supabase's own OAuth 2.1 Server. Dynamic client registration is on for
  that server, a deliberate tradeoff: any OAuth client can self register and ask a user to
  approve access under a self declared name, since we do not control claude.ai's callback
  URL in advance to hardcode it instead. The `/oauth/consent` page in `apps/web` is the
  only defense, it must always show the requesting client's real name and scopes before
  approval. Do not add an auto approve path, do not skip or shortcut that screen.
- Transcripts are never written to the database. Only capsules and their embeddings are.
  The fidelity check receives the transcript from the client and does not store it.
- Every number in the UI is computed at runtime. No fabricated metrics, ever.

## Writing
- No em dashes. No hyphenated compound words. Sentence case headings.
- Short human style variable names, no comments unless asked.
