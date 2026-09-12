# Carryover

Your AI gets measurably worse before it runs out of room. Carryover tells you when to
move, and moves the thinking for you.

Live: https://carryover-kxq7.onrender.com

Built in one afternoon at the Airtribe x Render Ship Room hackathon, Bengaluru, 12 Sep 2026.

## The one core action

Paste a long AI chat. Carryover shows an estimated health verdict as you paste, then
compresses the chat into a capsule: goal, state, decisions with reasons, approaches
already ruled out, constraints, open threads and the single next action. It renders that
capsule as a resume prompt for Claude, ChatGPT or Cursor. Copy it into a fresh session and
keep working.

Then press Check fidelity. A second model call writes three questions the original chat
answers and tries to answer them from the capsule alone. You get a real count, not a
promise.

Your transcript is never written to the database. Only the capsule is.

## Run it locally

Needs uv and a Gemini API key.

```
export GEMINI_API_KEY=...
uv run --frozen uvicorn main:app --port 8000
```

Open http://localhost:8000. Check `/healthz` returns `{"ok": true, "key": true}`, then make
one capsule, because a green health check only proves the key is present.

## Environment

| Var | Default | What it does |
|---|---|---|
| `GEMINI_API_KEY` | none | required |
| `GEMINI_MODEL` | `gemini-3.6-flash` | long transcripts and the fidelity check |
| `GEMINI_LITE` | `gemini-3.1-flash-lite` | transcripts at or below `ROUTE_AT` characters |
| `ROUTE_AT` | `40000` | router threshold in characters |
| `GEMINI_EMBED` | `gemini-embedding-001` | capsule embeddings for search |
| `DB_PATH` | `/tmp/carryover.db` | SQLite file, ephemeral on Render |
| `PORT` | `10000` | set by Render |

## Stack

FastAPI, Pydantic, uvicorn, SQLite, one HTML file with vanilla JS. Every model and
embedding call goes through stdlib urllib. No other dependencies.

## Research behind the meter

Hong, Troynikov and Huber, Context Rot, Chroma, 2025. Liu et al., Lost in the Middle,
TACL 2024. The 40 and 60 percent thresholds are our own estimates informed by those and
are labelled estimated in the UI.
