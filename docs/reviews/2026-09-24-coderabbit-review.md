# Review of the monorepo merge, 24 Sep 2026

Rakesh, these are my notes on PR #1 (13ed5b3 to f507f61). I ran CodeRabbit over the whole diff, then checked each finding against the code myself, because review bots get some things wrong. Everything below I could confirm. Line numbers are from f507f61.

Three findings are security issues on the live site. The repo is public, so I put those in a private security advisory on this repo instead. You should have access. Start with those.

After that, I'd fix the three items that lose data without telling anyone.

## What's good

Splitting `main.py` into modules made the code much easier to follow. `capsules.py` is the core and the rest are thin entry points or adapters, which is how I'd want it. Checking JWTs against Supabase's published keys with a cached `PyJWKClient` means the API holds no auth secret at all. The OAuth consent page is short and readable.

## Data that gets lost quietly

### The resume prompt stops early when one section is long

`render()` in `apps/api/app/capsules.py` goes through the fields in order and hits `break` at line 75 as soon as one block would go over the budget. If a capsule has a long decisions list, the constraints, ruled out approaches and literals after it never reach the prompt. Those are the parts a resumed session needs most. Skipping or trimming the oversized block and carrying on would fix it.

### A failed embedding makes the capsule vanish from search

`embed()` in `gemini.py` catches every exception and returns `None` (lines 104 to 105). `make_capsule` saves the row anyway (`capsules.py` line 97 onward), and search skips rows without an embedding. Nobody finds out. It should at least log the failure. Retrying, or failing the save, would be better.

### Retries create duplicates

Ids are random (`secrets.token_urlsafe(6)`, line 96). When a client times out and retries a save, we pay Gemini again and store a second copy. If the id were a hash of owner, transcript and parent, the retry would get back the row we already have. mem0 does this with an md5 of the text (`mem0/memory/main.py` line 1022) and Cognee's docs say its `add()` deduplicates by content hash.

## Errors that come back as a 500

- `gemini.py` line 89 reads `out["candidates"][0]` without checking. When Gemini blocks a response or returns nothing, that raises and the MCP client gets a 500. The function only catches `HTTPError` (line 87), so a timeout also ends up as a 500.
- `mcp.py` line 52 calls `m.get(...)` on whatever JSON arrived. A JSON array or a string raises `AttributeError`, which becomes a 500 instead of a JSON-RPC error.
- `mcp.py` line 33 passes `target` straight into `render()`. The web route checks it against the three dialects and the MCP path doesn't, so `target: "gemini"` raises `KeyError`.

## One slow save blocks the whole server

`/mcp` is `async def` (`mcp.py` line 41), but the work under it blocks: the Gemini call with its 90 second timeout, the embedding call and the database. FastAPI runs plain `def` routes in a thread pool and runs `async def` routes on the event loop. So while one save waits on Gemini, every other request waits too, `/healthz` included. Making it a plain `def` and reading the body without `await` should be enough.

## Smaller things

- Nit: at a budget of 600 or less, `render()` keeps only goal, state, next action and decisions (`capsules.py` line 30), which drops constraints and literals. MCP always passes 2000, so this only affects someone calling the resume route with a small budget.
- Nit: `routes.py` line 49 counts a check as passed when `preserved` is truthy. A model that answers `"false"` as a string counts as a pass. `is True` avoids it.
- Nit: in `apps/web/app/account/copy-block.tsx` line 9, a failed clipboard write (some browsers block it) rejects with nothing catching it, so the button does nothing. A short "copy it by hand" message would help.
- Nit: the not found message at `capsules.py` line 110 still says the capsule "may have expired on a redeploy". That stopped being true when we moved off SQLite on Render.
- FYI: `AGENTS.md` line 107 says the JWT verification secret must match in both apps. The API uses Supabase's public keys now and holds no secret. Only the Supabase project has to match.
- FYI: the landing page (`apps/web/app/page.tsx` line 62) promises a fidelity check. It only exists on the old page at `/`, which uses the anonymous routes, and no MCP tool exposes it. Connector users can't reach it.
- FYI: `apps/api` has no tests.

## What I left out

CodeRabbit flagged three things in `apps/api/app/index.html`: the token window estimate, an empty conversation list, and an unchecked response. That page is the old hackathon UI, so I skipped them. It also asked for an expiry note on the account page, which line 39 already has.

If something here is wrong, say so on the PR. I'd rather fix the review than have you chase a problem that isn't there.
