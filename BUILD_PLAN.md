# Build plan, 12:35 to 14:00 IST

Historical. This is the hackathon timebox from 12 Sep 2026, kept as a record of how the
app was originally built. It is not a live plan, see `AGENTS.md` and `SPEC.md` for the
current state of the repo.

Submit by 13:45. Demo at 14:00. Team of three.

## Rule that overrides everything

Deploy first, features second. A live URL with two features beats a better app that is
still local at 13:45. Every block below ends with a push. If a block runs over its box,
ship what works and move on.

## Timeline

| Time | Block | Owner |
|---|---|---|
| 12:35 to 12:45 | Repo, Render service, live URL with current code, `/healthz` returns `key: true` | A |
| 12:45 to 13:00 | Token meter and health verdict, client side, plus compression ratio | B |
| 12:45 to 13:05 | Fidelity check endpoint and its UI panel | C |
| 13:05 to 13:15 | Merge, redeploy, click through the whole flow on the live URL on a phone | A |
| 13:15 to 13:30 | Demo script written out loud and rehearsed once end to end | all |
| 13:30 to 13:40 | Last deploy. Nothing ships after this | A |
| 13:40 to 13:45 | Submission form: name, one liner, URL, who it is for, core action, screenshot | B |
| 13:45 to 14:00 | Rehearse twice more. Hit the URL every two minutes to keep the instance warm | all |

Parallel blocks B and C touch different files. B is `index.html` only. C adds one endpoint
to `main.py` plus one panel in `index.html`. Agree the panel's DOM id up front so the merge
is trivial. Suggested: `<div id="verify"></div>` directly under `#out`.

## Cut list, in the order things get cut

1. Budget selector for the window size, hardcode 200k
2. Cursor dialect, keep Claude and ChatGPT
3. Shareable `/c/{id}` link
4. Fidelity check entirely, if it is not working by 13:15

Never cut: the paste box, the capsule, the Claude resume prompt, the copy button.

## Deploy

Render, one web service, from the repo root.

```
Build command:  pip install -r requirements.txt
Start command:  uvicorn main:app --host 0.0.0.0 --port $PORT
Environment:    GEMINI_API_KEY = <key>
                PYTHON_VERSION = 3.11.9
```

Free instances sleep after inactivity and cold start takes close to a minute. From 13:45
onward, one person keeps a tab open and refreshes every two minutes. A judge hitting a
sleeping instance is the single most likely way to lose the Live Run points.

## Demo script, five minutes

1. Fifteen seconds on the problem. Not "chats run out of room" but "chats get worse before
   they run out of room, and you cannot see it happening". Cite that all 18 models tested
   by Chroma degrade as context grows.
2. Open the live URL on the projector. Paste a long real conversation. The health meter
   moves to "Hand off now" before you touch anything else. That is the hook.
3. Press the button. Capsule appears. Point at the ruled out approaches field and say
   nobody else captures this, because summaries keep what happened and drop what failed.
4. Show the fidelity check. Three questions, three passes, a real number.
5. Copy the Claude prompt, paste it into a fresh Claude chat on screen, ask a follow up
   that only works if the decisions carried over. Let the answer land without narrating it.
6. One line on what is next: the same capsule exposed over MCP so assistants save and load
   it themselves, no copy paste.

Hand the judge the URL and let them paste their own chat. That is the Finish the Job point.

## Rubric mapping

| Criterion | Points | How we earn it |
|---|---|---|
| Problem and impact | 30 | Context rot research, and everyone in the room has hit this |
| Product quality, one core action | 20 | Paste to resume prompt works end to end on real input |
| Live run | 20 | Render URL, no login, judge pastes their own chat |
| Outcome and polish | 20 | User leaves with a copied prompt and a working new session |
| Presentation | 10 | Rehearsed twice, live Claude paste as the closer |
