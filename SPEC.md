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

Path `/tmp/carryover.db`, override with `DB_PATH`. Render's filesystem is ephemeral, so
a redeploy wipes saved capsules. Accepted for the hackathon. Do not redeploy after 13:40.

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
| `GET /healthz` | `{ok, key}` where `key` reports whether GEMINI_API_KEY is set |
| `GET /` and `GET /c/{id}` | serve `index.html`, the second substitutes `__PRELOAD__` |

### P1, build first: token meter and compression ratio

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

### P1: server side source token count

`POST /api/capsule` stores `src_toks = ceil(len(transcript)/4)` in the row.
`GET /api/capsule/{id}` returns it so a shared link can show the same ratio.

### P2, build second: fidelity check

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

### P3, only if time remains

Copy button feedback, keyboard focus states, mobile stacking. All already partly present.

## Deliberately out of scope

MCP server. Browser extension. Accounts and auth. Capsule chaining across sessions. Team
sharing. `conversations.json` parsing. Vector search. Postgres. Anything with a queue.

Reasons are in RESEARCH.md. The short version: MCP cannot be judged in a browser, and the
rubric awards 20 points for a judge opening a Render URL and using the product directly.

## Environment

| Var | Required | Default |
|---|---|---|
| `GEMINI_API_KEY` | yes | none, `/healthz` reports false |
| `GEMINI_MODEL` | no | `gemini-2.5-flash` |
| `DB_PATH` | no | `/tmp/carryover.db` |
| `PORT` | set by Render | 10000 |

Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
