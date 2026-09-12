# Carryover

Web app that turns a dying AI chat session into a transferable context capsule, then
rehydrates it into a fresh session in Claude, ChatGPT or Cursor.

Built at the Airtribe x Render Ship Room hackathon, Bengaluru, 12 Sep 2026.
Hard deadline 13:45 IST. Demo 14:00 IST.

## Read these before touching code

- `agent_docs/SPEC.md` high level and low level design, every endpoint and function
- `agent_docs/BUILD_PLAN.md` the timeboxed order of work and what to cut when behind
- `agent_docs/RESEARCH.md` competitive landscape and the research that shapes the product
- `agent_docs/CONSTRAINTS.md` hackathon rubric, non negotiables, and the demo script

## Current state

Live at https://carryover-kxq7.onrender.com and deployed from https://github.com/Anonymus-Coder2403/carryover on every push to main.

`main.py` and `index.html` exist and implement capsule extraction plus multi target
rehydration. They are not yet deployed. Everything in SPEC.md marked P1 is unbuilt.

## Hard rules for this repo

- One Render web service. FastAPI serves the API and the page from the same process.
- No login, no accounts, no OAuth. A judge must use it with zero setup.
- No browser storage APIs. Server side SQLite only.
- No new dependencies beyond `fastapi`, `uvicorn`, `pydantic`. Use stdlib `urllib` for
  the model call so there is no SDK version risk during the build.
- Deploy after every completed step. A broken URL at 13:45 scores zero on 20 points.
- Never invent a metric. Every number shown in the UI is computed at runtime from real
  input.

## Style

- No em dashes. No hyphenated compound words, write "multi target" not "multi-target".
- Sentence case headings.
- Short human style variable names, no comments unless asked.
