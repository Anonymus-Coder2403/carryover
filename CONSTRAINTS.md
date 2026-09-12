# Non negotiables

## From the hackathon rubric
- Live at a Render URL by 13:45. Localhost scores zero on 20 points.
- No login wall. A judge opens it and uses it directly, no account, no API key.
- One core action must work end to end on real input.
- The user leaves with something done. Here that is a copied resume prompt that works.
- Nothing pre built. Everything in this repo ships today.

## Engineering
- One process, one Render service. FastAPI serves the API and the page.
- Dependencies capped at fastapi, uvicorn, pydantic. Model and embedding calls use stdlib urllib.
- uv only for packaging, locally and on Render. Never pip.
- Model names live in env vars, never in code. Test a model name with a real POST before
  it goes into the Render panel, the model list is per key and names get retired.
- No browser storage APIs anywhere.
- The database lives on a Render persistent disk at /var/data. Before 14:49 on 12 Sep 2026
  it was on /tmp and every deploy destroyed every capsule. That ceiling is closed, with no
  code change, by DB_PATH pointing at the disk.
- The MCP endpoint requires a bearer token from `MCP_TOKENS`, compared in constant time.
  Capsules saved through MCP are owned by the hash of the token that saved them, are
  invisible to the website and to every other token, and get no share link. Capsules
  made on the website stay public by link. Tokens live in Render's env panel and in the
  Claude connector's request header, never in a file, a commit or a chat.
- Transcripts are never written to the database. Only capsules and their embeddings are.
  The fidelity check receives the transcript from the client and does not store it.
  This is a claim made on stage, so it must stay true in code.
- Every number in the UI is computed at runtime. No fabricated metrics, ever.

## Writing
- No em dashes. No hyphenated compound words. Sentence case headings.
- Short human style variable names, no comments unless asked.
