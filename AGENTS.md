# Carryover

Web app that turns a dying AI chat session into a transferable context capsule, then
rehydrates it into a fresh session in Claude, ChatGPT or Cursor.

Built at the Airtribe x Render Ship Room hackathon, Bengaluru, 12 Sep 2026.
Hard deadline 13:45 IST. Demo 14:00 IST.

## Read these before touching code

All docs live at the repo root.

- `SPEC.md` high level and low level design, every endpoint and function
- `BUILD_PLAN.md` the timeboxed order of work and what to cut when behind
- `RESEARCH.md` competitive landscape and the research that shapes the product
- `CONSTRAINTS.md` hackathon rubric, non negotiables, and the demo script

## Current state

Live at https://carryover-kxq7.onrender.com from https://github.com/Anonymus-Coder2403/carryover.

Deployed by Manual Deploy only. Pushes do not auto deploy, the service was connected as a
public repo rather than through the GitHub app. Verify what is actually live by byte comparing
the served page against `git show <sha>:index.html`, never from memory of having pushed.
Since 14:49 on 12 Sep 2026 the database lives on a 1 GB Render persistent disk at
`/var/data/carryover.db` via `DB_PATH`, proven by making a capsule, redeploying, and
loading it again. Deploys no longer destroy data. Zero downtime deploys are off because
of the disk, so every deploy has a short outage.

MCP server at `POST /mcp`, streamable HTTP, stateless, plain JSON, two tools:
`save_capsule` and `load_capsule`. Same process, same functions, no SDK.

Shipped and verified on the live URL: capsule extraction, multi target rehydration, the
token meter and health verdict (P1), the fidelity check (P2), a length based model router,
a client side file parser for ChatGPT and Claude exports, and cosine search over saved
capsules using Gemini embeddings.

Models are env vars. `GEMINI_MODEL` (default gemini-3.6-flash) handles transcripts over
`ROUTE_AT` characters (default 40000) and the fidelity check. `GEMINI_LITE` (default
gemini-3.1-flash-lite) handles everything shorter. `GEMINI_EMBED` (default
gemini-embedding-001) embeds capsules. gemini-2.5-flash is retired for new keys and
gemini-3.5-flash-lite returned malformed JSON in testing, do not use either.

## Hard rules for this repo

- One Render web service. FastAPI serves the API and the page from the same process.
- No login, no accounts, no OAuth. A judge must use it with zero setup.
- No browser storage APIs. Server side SQLite only.
- No new dependencies beyond `fastapi`, `uvicorn`, `pydantic`. Use stdlib `urllib` for
  every Gemini call, generation and embeddings, so there is no SDK version risk.
- uv only. `uv lock` after any pin change, `uv run --frozen` locally. Never pip, never
  `uv pip`. Render builds with `uv sync --frozen` and starts with `uv run --frozen uvicorn`.
- Postgres stays out. SQLite on the persistent disk with a linear cosine scan is enough
  until there are thousands of capsules.
- The dependency cap held through every feature. Cosine search is pure Python, no numpy.
  Keep it that way until a measurement says otherwise.
- Deploy after every completed step. A broken URL at 13:45 scores zero on 20 points.
- Never invent a metric. Every number shown in the UI is computed at runtime from real
  input.

## Style

- No em dashes. No hyphenated compound words, write "multi target" not "multi-target".
- Sentence case headings.
- Short human style variable names, no comments unless asked.
