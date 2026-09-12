import os, json, sqlite3, secrets, re, hmac, hashlib, urllib.request, urllib.error
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, Response
from pydantic import BaseModel

DB = os.environ.get("DB_PATH", "/tmp/carryover.db")
KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
LITE = os.environ.get("GEMINI_LITE", "gemini-3.1-flash-lite")
ROUTE_AT = int(os.environ.get("ROUTE_AT", "0"))
EMBED = os.environ.get("GEMINI_EMBED", "gemini-embedding-001")
TOKENS = [t.strip() for t in os.environ.get("MCP_TOKENS", "").split(",") if t.strip()]

app = FastAPI()


def db():
    c = sqlite3.connect(DB)
    c.execute("create table if not exists caps (id text primary key, data text, created text default current_timestamp)")
    cols = [r[1] for r in c.execute("pragma table_info(caps)")]
    if "emb" not in cols:
        c.execute("alter table caps add column emb text")
    if "owner" not in cols:
        c.execute("alter table caps add column owner text")
    return c


SCHEMA = """{
 "title": "short name for this work",
 "goal": "one sentence, what this session is trying to achieve",
 "state": "where the work actually stands right now",
 "decisions": [{"choice": "", "why": ""}],
 "rejected": [{"approach": "", "why_failed": ""}],
 "constraints": ["hard rules the user set that must carry over"],
 "artifacts": [{"name": "", "kind": "", "where": ""}],
 "open_threads": ["unresolved questions"],
 "next_action": "the single next step",
 "literals": ["every exact URL, id, file path, command, env var name, model name or config string from the transcript, verbatim, one per entry"],
 "glossary": [{"term": "", "means": ""}]
}"""

EXTRACT = """You compress a dying AI chat session into a transferable context capsule.

The next assistant will read only your capsule, never this transcript. Capture what is
expensive to rediscover: decisions and the reasoning behind them, approaches already ruled
out, constraints the user imposed, and exactly where the work stands.

Drop pleasantries, restated code the user already has, and anything the next assistant can
re-derive in one step.

Never drop literal values. URLs, ids, file paths, commands, env var names, model names and
config strings go into the capsule verbatim, in artifacts or constraints, because they are
the most expensive things to rediscover. Never paraphrase a URL as "the provided URLs".

Return only JSON matching this shape, no prose, no code fences:
""" + SCHEMA + """

TRANSCRIPT:
"""


def route(text):
    return MODEL if len(text) > ROUTE_AT else LITE


def gemini(prompt, model=None):
    if not KEY:
        raise HTTPException(500, "GEMINI_API_KEY is not set on the server")
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (model or MODEL, KEY)
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            out = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(502, "Model call failed: %s" % e.read().decode()[:300])
    txt = out["candidates"][0]["content"]["parts"][0]["text"]
    txt = re.sub(r"^```(json)?|```$", "", txt.strip()).strip()
    try:
        return json.loads(txt)
    except ValueError:
        raise HTTPException(502, "Model returned malformed JSON. Try again.")


def embed(text):
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:embedContent?key=%s" % (EMBED, KEY)
    body = json.dumps({"content": {"parts": [{"text": text[:8000]}]}}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())["embedding"]["values"]
    except Exception:
        return None


def owner_of(req):
    auth = req.headers.get("authorization", "")
    tok = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    for t in TOKENS:
        if tok and hmac.compare_digest(t, tok):
            return hashlib.sha256(tok.encode()).hexdigest()[:12]
    return None


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def blank(c):
    d = {"title": "", "goal": "", "state": "", "decisions": [], "rejected": [], "constraints": [],
         "artifacts": [], "open_threads": [], "next_action": "", "literals": [], "glossary": []}
    d.update({k: v for k, v in c.items() if k in d and v})
    return d


def render(c, target, budget):
    c = blank(c)
    order = ["goal", "state", "next_action", "decisions", "constraints", "rejected",
             "literals", "open_threads", "artifacts", "glossary"]
    if budget <= 600:
        order = order[:4]
    elif budget <= 2200:
        order = order[:8]

    def lines(k):
        v = c.get(k)
        if not v:
            return []
        if k == "decisions":
            return ["%s. Reason: %s" % (d.get("choice", ""), d.get("why", "")) for d in v]
        if k == "rejected":
            return ["%s. Failed because: %s" % (d.get("approach", ""), d.get("why_failed", "")) for d in v]
        if k == "artifacts":
            return ["%s (%s) at %s" % (d.get("name", ""), d.get("kind", ""), d.get("where", "")) for d in v]
        if k == "glossary":
            return ["%s means %s" % (d.get("term", ""), d.get("means", "")) for d in v]
        if isinstance(v, list):
            return [str(x) for x in v]
        return [str(v)]

    names = {"goal": "Goal", "state": "Where the work stands", "next_action": "Next action",
             "decisions": "Decisions already made", "constraints": "Constraints that still apply",
             "rejected": "Approaches already ruled out", "literals": "Exact values, use verbatim",
             "open_threads": "Still unresolved",
             "artifacts": "Artifacts", "glossary": "Terms"}

    head = {
        "claude": "You are picking up work that was in progress in another assistant. The previous session hit its context limit. Everything known is below. Continue from the next action without asking me to re-explain.",
        "chatgpt": "Resume in-progress work from another assistant that ran out of context. Full state is below. Continue from the next action. Do not re-ask what is already stated.",
        "cursor": "Project context carried over from a previous AI session. Treat the decisions and constraints as binding. Continue from the next action.",
    }[target]

    body, used = [], 0
    for k in order:
        ls = lines(k)
        if not ls:
            continue
        if target == "claude":
            block = "<%s>\n%s\n</%s>" % (k, "\n".join(ls), k)
        elif target == "chatgpt":
            block = "## %s\n%s" % (names[k], "\n".join("- " + l for l in ls))
        else:
            block = "# %s\n%s" % (names[k], "\n".join("- " + l for l in ls))
        if used + len(block) > budget * 4:
            break
        body.append(block)
        used += len(block)

    title = c.get("title") or "Carried-over session"
    return "%s\n\nSession: %s\n\n%s\n\nBegin by confirming in one line that you have the context, then do the next action." % (head, title, "\n\n".join(body))


class In(BaseModel):
    transcript: str


def make_capsule(transcript, owner=None):
    t = transcript.strip()
    if len(t) < 80:
        raise HTTPException(400, "Paste more of the conversation. At least a few exchanges.")
    model = route(t)
    cap = blank(gemini(EXTRACT + t[:120000], model))
    cid = secrets.token_urlsafe(6)
    emb = embed(json.dumps(cap))
    c = db()
    c.execute("insert into caps (id, data, emb, owner) values (?, ?, ?, ?)", (cid, json.dumps(cap), json.dumps(emb) if emb else None, owner))
    c.commit()
    c.close()
    return {"id": cid, "capsule": cap, "model": model}


@app.post("/api/capsule")
def make(i: In):
    return make_capsule(i.transcript)


def load(cid, owner=None):
    c = db()
    r = c.execute("select data, owner from caps where id=?", (cid,)).fetchone()
    c.close()
    if r and r[1] and r[1] != owner:
        r = None
    if not r:
        raise HTTPException(404, "No capsule with that id. It may have expired on a redeploy.")
    return json.loads(r[0])


@app.get("/api/capsule/{cid}")
def get(cid: str):
    return {"id": cid, "capsule": load(cid)}


@app.get("/api/resume/{cid}", response_class=PlainTextResponse)
def resume(cid: str, target: str = "claude", budget: int = 2000):
    if target not in ("claude", "chatgpt", "cursor"):
        raise HTTPException(400, "target must be claude, chatgpt or cursor")
    return render(load(cid), target, budget)


VERIFY = """You are testing whether a compressed context capsule preserved what mattered.

Write three questions that the ORIGINAL transcript answers and that a person resuming
this work would need to know. Prefer questions about decisions, ruled out approaches and
constraints over questions about facts that are easy to look up.

Then answer each question using ONLY the capsule. If the capsule does not contain the
answer, say so plainly and mark it not preserved.

Return only JSON:
{"checks":[{"q":"","a":"","preserved":true}],"verdict":"one line"}

TRANSCRIPT:
%s

CAPSULE:
%s
"""


@app.post("/api/verify/{cid}")
def verify(cid: str, i: In):
    cap = load(cid)
    out = gemini(VERIFY % (i.transcript.strip()[:120000], json.dumps(cap)))
    checks = [c for c in out.get("checks", []) if isinstance(c, dict)][:3]
    return {"checks": checks, "verdict": out.get("verdict", ""),
            "passed": sum(1 for c in checks if c.get("preserved")), "total": len(checks)}


def search_caps(q, owner=None):
    qe = embed(q.strip())
    if not qe:
        raise HTTPException(502, "Embedding call failed")
    c = db()
    rows = c.execute("select id, data, emb from caps where emb is not null and owner is ?", (owner,)).fetchall()
    c.close()
    # ponytail: linear scan over sqlite rows, move to a vector index past a few thousand capsules
    hits = []
    for cid, data, emb in rows:
        cap = json.loads(data)
        hits.append({"id": cid, "title": cap.get("title", ""), "goal": cap.get("goal", ""), "score": round(cosine(qe, json.loads(emb)), 3)})
    hits.sort(key=lambda h: -h["score"])
    return {"hits": hits[:5]}


@app.get("/api/search")
def search(q: str):
    return search_caps(q)


TOOLS = [
    {"name": "save_capsule",
     "description": "Compress a chat transcript into a private context capsule owned by this connector. Returns the capsule id and the capsule itself. The transcript is never stored.",
     "inputSchema": {"type": "object", "properties": {"transcript": {"type": "string", "description": "The full chat, both sides"}}, "required": ["transcript"]}},
    {"name": "load_capsule",
     "description": "Load a saved capsule as a resume prompt by id, or search saved capsules by meaning with a query. Give one of id or query.",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "string", "description": "Capsule id from save_capsule"},
         "query": {"type": "string", "description": "What the work was about, used for search when id is not known"},
         "target": {"type": "string", "enum": ["claude", "chatgpt", "cursor"], "description": "Prompt dialect, default claude"}}}},
]


def tool(name, a, owner):
    if name == "save_capsule":
        r = make_capsule(a.get("transcript", ""), owner)
        return json.dumps({"id": r["id"], "model": r["model"], "private": True, "capsule": r["capsule"]}, indent=1)
    if name == "load_capsule":
        if a.get("id"):
            return render(load(a["id"], owner), a.get("target", "claude"), 2000)
        if a.get("query"):
            return json.dumps(search_caps(a["query"], owner), indent=1)
        raise HTTPException(400, "Give an id or a query")
    raise HTTPException(404, "Unknown tool: %s" % name)


@app.post("/mcp")
async def mcp(req: Request):
    owner = owner_of(req)
    if not owner:
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32001, "message": "Unauthorized. Send Authorization: Bearer <token>."}, "id": None},
                            401, headers={"WWW-Authenticate": "Bearer"})
    try:
        m = await req.json()
    except ValueError:
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None}, 400)
    method, rid, params = m.get("method", ""), m.get("id"), m.get("params") or {}
    if method.startswith("notifications/"):
        return Response(status_code=202)
    if method == "initialize":
        result = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                  "serverInfo": {"name": "carryover", "version": "0.1.0"},
                  "instructions": "Use save_capsule when a conversation is getting long and the user wants to continue elsewhere. Use load_capsule to resume from a capsule id or find one by query."}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            text = tool(params.get("name"), params.get("arguments") or {}, owner)
            result = {"content": [{"type": "text", "text": text}], "isError": False}
        except HTTPException as e:
            result = {"content": [{"type": "text", "text": e.detail}], "isError": True}
    else:
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found: %s" % method}, "id": rid})
    return JSONResponse({"jsonrpc": "2.0", "result": result, "id": rid})


@app.get("/mcp")
def mcp_get():
    return Response(status_code=405)


@app.get("/healthz")
def health():
    return {"ok": True, "key": bool(KEY)}


PAGE = open(os.path.join(os.path.dirname(__file__), "index.html")).read()


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE


@app.get("/c/{cid}", response_class=HTMLResponse)
def shared(cid: str):
    load(cid)
    return PAGE.replace("__PRELOAD__", cid)
