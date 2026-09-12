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
- Transcripts are never written to the database. Only capsules and their embeddings are.
  The fidelity check receives the transcript from the client and does not store it.
  This is a claim made on stage, so it must stay true in code.
- Every number in the UI is computed at runtime. No fabricated metrics, ever.

## Writing
- No em dashes. No hyphenated compound words. Sentence case headings.
- Short human style variable names, no comments unless asked.
