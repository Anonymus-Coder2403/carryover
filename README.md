# Carryover

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-3ECF8E?logo=supabase&logoColor=white)
![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-server-6E56CF)

Your AI gets measurably worse before it runs out of room. Carryover tells you when to
move, and moves the thinking for you.

Paste a long AI chat, or drop in a ChatGPT or Claude data export. Carryover compresses it
into a small context capsule (goal, decisions made, approaches already ruled out,
constraints, open threads, the single next action, every URL and id kept verbatim) and
turns that into a resume prompt for Claude, ChatGPT or Cursor. Paste the prompt into a
fresh session and keep working, without explaining anything again.

Press Check fidelity and a second pass writes three questions the original chat answers,
then tries to answer them from the capsule alone. You get a real score, not a promise. When
that new session fills up too, chain the next capsule from the current one and it carries
every decision and rejection forward.

Carryover also runs as an MCP server, so an AI assistant can save and load capsules for you
directly, no copy and paste.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI, uvicorn, Pydantic, SQLAlchemy |
| Database | Postgres on Supabase |
| Auth | Supabase Auth, OAuth 2.1 for claude.ai and ChatGPT, JWKS verified bearer tokens for Claude Code and Claude Desktop |
| Model calls | Gemini, stdlib `urllib`, no SDK |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind |
| Package management | `uv` for the backend, `npm` for the frontend |

## What it does

- **Compress.** One model call turns a transcript into a structured capsule instead of a
  wall of text.
- **Rehydrate.** The same capsule renders as a resume prompt in three dialects (Claude,
  ChatGPT, Cursor), picked instantly, no extra model call.
- **Verify.** A fidelity check scores how much of what mattered survived compression.
- **Chain.** Link capsules across sessions so a third session knows what the first one
  decided.
- **Search.** Find an old capsule by what it was about, not by remembering its id.
- **Use from your assistant.** `save_capsule` and `load_capsule` as MCP tools, so an
  assistant can do this for you mid conversation.

Your transcript is never written to the database, only the capsule is.

## Add it to your coding assistant

Sign up at the web app, log in, and open `/account` for a bearer token and a ready made
config. Every client below ends up calling the same two tools: `save_capsule` and
`load_capsule`. Capsules are private to your account, no one else can load yours even with
the id.

**Claude Code**

```
claude mcp add --transport http carryover <api url>/mcp --header "Authorization: Bearer <token>"
```

**Claude Desktop**, in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "carryover": {
      "type": "http",
      "url": "<api url>/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

**claude.ai and ChatGPT (the websites)**

Add `<api url>/mcp` as a custom connector, no token to copy. Both sign in with OAuth: it
sends you through login and a one time consent screen, then you're connected under the
same account.

Tokens expire after about an hour. If calls start failing, log in again on `/account` for
a fresh one, or reconnect on claude.ai/ChatGPT if you're on OAuth.

## Run it locally

Needs `uv`, `npm`, a free [Supabase](https://supabase.com) project, and a
[Gemini API key](https://aistudio.google.com/apikey).

**1. Supabase project.** From its dashboard, grab:

- **Settings → Database → Connection pooling → Session pooler**, the connection string
  (use the pooler, the direct connection is IPv6 only and fails to resolve on a lot of
  networks)
- **Settings → Data API**, the Project URL and the anon public key

**2. Backend**

```
cd apps/api
cp .env.example .env.local
```

Fill in `.env.local`:

```
DATABASE_URL=postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
SUPABASE_URL=https://<ref>.supabase.co
PUBLIC_API_URL=http://localhost:8000
GEMINI_API_KEY=<your key>
```

```powershell
Get-Content .env.local | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { Set-Item -Path "Env:$($matches[1])" -Value $matches[2] } }
uv run --frozen uvicorn app.main:app --port 8000
```

(bash/zsh: `set -a; source .env.local; set +a` then the same `uv run` line.)

Check `curl http://localhost:8000/healthz` returns `{"ok": true, "key": true}`.

**3. Frontend**

```
cd apps/web
cp .env.example .env.local
```

Fill in `.env.local`:

```
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key>
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```
npm install
npm run dev
```

Open `http://localhost:3000`, sign up, log in, visit `/account` for your token.

**4. Connect claude.ai or ChatGPT locally (optional).** Both are cloud services and can't
reach `localhost`, so either deploy for real or expose your local API with a tunnel
(`ngrok http 8000`), then restart the API with `PUBLIC_API_URL` set to the tunnel's URL. In
Supabase, **Authentication → OAuth Server**, enable it with `authorization_url_path` set to
`/oauth/consent` and `allow_dynamic_registration` on, and set **Authentication → URL
Configuration → Site URL** to wherever your frontend is running.

## Docs

- [`SPEC.md`](SPEC.md), every endpoint and function
- [`AGENTS.md`](AGENTS.md), architecture and the hard rules for this repo
- [`CONSTRAINTS.md`](CONSTRAINTS.md), non negotiables and the incidents that shaped them
- [`RESEARCH.md`](RESEARCH.md), the research behind the token meter
