# Review of the monorepo merge, 24 Sep 2026

Rakesh, these are my notes on PR #1 (13ed5b3 to f507f61). I ran CodeRabbit over the whole diff, then checked each finding against the code myself, because review bots get some things wrong. I also added a few things I noticed while reading the same files. Line numbers are from f507f61.

For most of these I didn't stop at reading the code. I called the functions directly with dummy settings and no network, and I've pasted what came back. Where I only read the code, I say so.

Three findings are security issues on the live site. The repo is public, so those are in a private security advisory on this repo instead of here. You should have access. Start with those.

After that I'd fix numbers 1 to 3, because they lose data without anyone finding out.

## What's good

Splitting `main.py` into modules made the code much easier to follow. `capsules.py` is the core and the rest are thin entry points or adapters, which is how I'd want it. Checking JWTs against Supabase's published keys with a cached `PyJWKClient` means the API holds no auth secret at all. The OAuth consent page is short and readable.

## The list

| # | Finding | Where | Severity | Found by |
|---|---|---|---|---|
| 1 | One long section wipes the rest of the resume prompt | `capsules.py:74-75` | High | CodeRabbit |
| 2 | A failed embedding hides the capsule from search | `gemini.py:104-105`, `capsules.py:97-100` | High | CodeRabbit |
| 3 | Retrying a save pays twice and stores a duplicate | `capsules.py:96` | Medium | me |
| 4 | A blocked or timed out Gemini call becomes a 500 | `gemini.py:85-89` | Medium | CodeRabbit, me |
| 5 | A JSON body that isn't an object becomes a 500 | `mcp.py:49-52` | Low | CodeRabbit |
| 6 | An unknown `target` over MCP becomes a 500 | `mcp.py:33` | Low | me |
| 7 | One slow save stalls every other request | `mcp.py:41` | High | me |
| 8 | Small budgets drop constraints and literals | `capsules.py:30-31` | Low | CodeRabbit |
| 9 | The string "false" counts as a passed check | `routes.py:49` | Low | CodeRabbit |
| 10 | The copy button fails silently | `copy-block.tsx:9` | Low | CodeRabbit |
| 11 | The not found message talks about redeploys | `capsules.py:110` | Low | me |
| 12 | AGENTS.md still mentions a shared JWT secret | `AGENTS.md:107-108` | Low | CodeRabbit |
| 13 | The landing page promises a fidelity check MCP users can't reach | `apps/web/app/page.tsx:62` | Medium | me |
| 14 | `apps/api` has no tests | n/a | Medium | me |

Severity is my own call, based on what a user loses. CodeRabbit's labels are in the raw output if you want them.

## Data that gets lost quietly

### 1. One long section wipes the rest of the resume prompt

High. `apps/api/app/capsules.py`, lines 74 to 75. Checked by running it.

`render()` builds the prompt one field at a time, in this order: goal, state, next action, decisions, constraints, rejected, literals, open threads. As soon as one block would push the total past `budget * 4` characters, it stops:

```python
        if used + len(block) > budget * 4:
            break
```

So a long block doesn't just get dropped. Everything after it goes too. I gave it a capsule with 30 long decisions, one constraint and one URL literal, at the budget MCP uses (2000):

```
render len 386 | has constraints: False | has literal: False | has decisions: False
```

The prompt came back with only the header, goal, state and next action. The decisions, the constraint and the URL were all gone, and nothing tells the user. Constraints and literals are the parts a resumed session needs most.

The smallest fix is `continue` instead of `break`, so an oversized block is skipped and the smaller ones after it still fit:

```python
        if used + len(block) > budget * 4:
            continue
```

A better one trims the long list to fit rather than skipping it. I'd start with `continue`, since it's one word.

### 2. A failed embedding hides the capsule from search

High. `apps/api/app/gemini.py` lines 104 to 105, and `capsules.py` lines 97 to 100. Checked by running it.

`embed()` catches every exception and returns `None`:

```python
    except Exception:
        return None
```

`make_capsule` saves the row anyway with `emb=None`, and `search_caps` only looks at rows where `emb` isn't null (`capsules.py` line 120). So if the embedding call times out, the save looks fine to the user, the capsule exists, and search will never find it. When I made `urlopen` raise a timeout, `embed("hi")` returned `None` with no log line.

At minimum, log it so we can see how often it happens:

```python
    except Exception as e:
        print("embed failed: %r" % e)
        return None
```

Later, a small job could re-embed rows where `emb is null`. Failing the whole save is the other option, but that throws away a capsule the user already paid for.

### 3. Retrying a save pays twice and stores a duplicate

Medium. `apps/api/app/capsules.py`, line 96. Read, not run, because running it costs a real Gemini call.

The id is random:

```python
    cid = secrets.token_urlsafe(6)
```

A save takes 10 to 13 seconds, so clients do time out and retry. Each retry runs the whole extraction again, pays Gemini again, and stores a second row with a new id. Both rows then show up in search.

If the id comes from the content, a retry can find the first row and return it before calling Gemini:

```python
    raw = "%s|%s|%s" % (owner, t[:120000], parent or "")
    cid = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())[:22].decode()
    with Session() as s:
        row = s.get(Capsule, cid)
    if row:
        return {"id": cid, "capsule": row.data, "model": None, "parent": row.parent}
```

It needs `import base64, hashlib` at the top of the file. It also has to sit near the top of `make_capsule`, before the Gemini call, or it saves nothing. As a side effect, new ids go from 48 bits to 132. mem0 dedupes the same way (an md5 of the text, `mem0/memory/main.py` line 1022), and Cognee's docs say its `add()` skips content it has seen by hash.

## Errors that come back as a 500

### 4. A blocked or timed out Gemini call becomes a 500

Medium. `apps/api/app/gemini.py`, lines 85 to 89. Checked by running it.

`gemini()` only catches `HTTPError`, then reads the text without checking it's there:

```python
    except urllib.error.HTTPError as e:
        raise HTTPException(502, "Model call failed: %s" % e.read().decode()[:300])
    txt = out["candidates"][0]["content"]["parts"][0]["text"]
```

I tried two cases:

```
gemini on timeout -> TimeoutError | is HTTPException: False
gemini blocked -> KeyError 'candidates'
```

`tool()` in `mcp.py` only turns `HTTPException` into a tool error, so both of these escape as a plain 500 and the connector shows something generic. The second one is what Gemini sends when it blocks a prompt: `promptFeedback` and no `candidates`.

Suggested fix:

```python
    except urllib.error.HTTPError as e:
        raise HTTPException(502, "Model call failed: %s" % e.read().decode()[:300])
    except (urllib.error.URLError, TimeoutError) as e:
        raise HTTPException(504, "Model call failed: %s" % e)
    try:
        txt = out["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise HTTPException(502, "Model returned no text: %s" % out.get("promptFeedback", ""))
```

`HTTPError` is a subclass of `URLError`, so it has to stay first.

### 5. A JSON body that isn't an object becomes a 500

Low. `apps/api/app/mcp.py`, lines 49 to 52. Checked by running the same call.

```python
        m = await req.json()
    ...
    method, rid, params = m.get("method", ""), m.get("id"), m.get("params") or {}
```

Valid JSON that isn't an object gets past the parse check. A list gives:

```
list body -> AttributeError 'list' object has no attribute 'get'
```

Only an authenticated caller can reach this line, so it's not an attack surface, but a client that sends a JSON-RPC batch (an array) gets a 500 instead of an error it can read. After the parse:

```python
    if not isinstance(m, dict):
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": None}, 400)
```

### 6. An unknown `target` over MCP becomes a 500

Low. `apps/api/app/mcp.py`, line 33. Checked by running it.

```python
            return render(load(a["id"], owner), a.get("target", "claude"), 2000)
```

The web route checks `target` first (`routes.py` lines 38 to 39). The MCP path doesn't, and `render()` looks it up in a dict:

```
target gemini -> KeyError 'gemini'
```

The tool schema lists the three allowed values, but a client or model can still send something else. The same check the web route does fixes it:

```python
            t = a.get("target", "claude")
            if t not in ("claude", "chatgpt", "cursor"):
                raise HTTPException(400, "target must be claude, chatgpt or cursor")
            return render(load(a["id"], owner), t, 2000)
```

## One slow save stalls every other request

### 7. `/mcp` is async but everything under it blocks

High. `apps/api/app/mcp.py`, line 41. Read, not run. Proving it needs two real saves at once.

```python
@router.post("/mcp")
async def mcp(req: Request):
```

Everything this handler calls is blocking: `owner_of` can fetch Supabase's keys over the network, `gemini()` waits up to 90 seconds, `embed()` up to 20, and the database calls are synchronous SQLAlchemy. FastAPI runs a plain `def` route in a thread pool, but it runs an `async def` route on the event loop. So while one save sits in `gemini()`, the loop can't take any other request, `/healthz` included. We run a single uvicorn process with no `--workers`, so every user waits.

Changing it to a plain `def` doesn't work cleanly, because the handler needs `await req.json()`. The smaller fix keeps it async and hands the blocking calls to a thread:

```python
from starlette.concurrency import run_in_threadpool

    owner = await run_in_threadpool(owner_of, req)
    ...
            text = await run_in_threadpool(tool, params.get("name"), params.get("arguments") or {}, owner)
```

`run_in_threadpool` ships with Starlette 0.41.3, which we already have.

## Smaller things

### 8. Small budgets drop constraints and literals

Low. `apps/api/app/capsules.py`, lines 30 to 31. Checked by running it.

```python
    if budget <= 600:
        order = order[:4]
```

At 600 or less, only goal, state, next action and decisions survive. Same capsule, two budgets:

```
budget 600 has constraints: False | budget 2000: True
```

MCP always passes 2000, so this only hits someone calling `/api/resume` with a small `budget`. If a short prompt is ever needed, I'd keep constraints over decisions.

### 9. The string "false" counts as a passed check

Low. `apps/api/app/routes.py`, line 49. Checked by running the same expression.

```python
            "passed": sum(1 for c in checks if c.get("preserved")), "total": len(checks)}
```

A model that answers `"preserved": "false"` as a string counts as a pass:

```
passed with string false: 2
```

`if c.get("preserved") is True` fixes it.

### 10. The copy button fails silently

Low. `apps/web/app/account/copy-block.tsx`, line 9. Read, not run.

```tsx
  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
```

Some browsers block clipboard writes, for example without permission or outside a secure context. When that happens the promise rejects, nothing catches it, and the button just doesn't react. Since this is where people copy their MCP config, a try/catch that says "copy it by hand" would save a confused user.

### 11. The not found message talks about redeploys

Low. `apps/api/app/capsules.py`, line 110.

```python
        raise HTTPException(404, "No capsule with that id. It may have expired on a redeploy.")
```

That was true with SQLite on Render, before the disk. With Postgres nothing expires, so something like "No capsule with that id for this account" is more accurate.

### 12. AGENTS.md still mentions a shared JWT secret

Low. `AGENTS.md`, lines 107 to 108.

It says "the JWT verification secret and Supabase project must match on both sides". The API checks tokens against Supabase's public keys (`auth.py` line 9), so the two apps no longer share a secret. Only the Supabase project has to match.

### 13. The landing page promises a fidelity check MCP users can't reach

Medium. `apps/web/app/page.tsx`, line 62.

The landing page says "A fidelity check answers questions from the original transcript using only the capsule". That check is `POST /api/verify/{cid}`, which only the old page at `/` calls, and no MCP tool exposes it. Anyone who signs up and uses Carryover through a connector can't run it. Since it's a public claim, either the copy changes or the check becomes an MCP tool.

### 14. `apps/api` has no tests

Medium.

`apps/api` has no test files at all. Every result above came from calling the functions by hand. Most of them could become a one line assert in a single `tests/test_capsules.py`: `render()` keeps constraints when decisions are long, `embed()` failure is logged, `gemini()` turns a blocked response into a 502. That file would catch 1, 4, 6, 8 and 9 coming back.

## What I left out

CodeRabbit flagged three things in `apps/api/app/index.html`: the token window estimate (lines 123 to 129), an empty conversation list (line 173), and an unchecked response (lines 206 to 207). That page is the old hackathon UI, so I skipped them. It also asked for an expiry note on the account page, which line 39 already has.

## How I checked

Everything marked "checked by running it" came from importing the modules in `apps/api/.venv` with dummy `DATABASE_URL`, `SUPABASE_URL` and `PUBLIC_API_URL`, then calling `render()`, `embed()` and `gemini()` directly, with `urllib.request.urlopen` replaced by a stub. Nothing touched the network or the database.

If something here is wrong, say so on the PR. I'd rather fix the review than have you chase a problem that isn't there.
