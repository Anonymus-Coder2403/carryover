import os, json, sqlite3, secrets, re, urllib.request, urllib.error
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

DB = os.environ.get("DB_PATH", "/tmp/carryover.db")
KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
LITE = os.environ.get("GEMINI_LITE", "gemini-3.1-flash-lite")
ROUTE_AT = int(os.environ.get("ROUTE_AT", "40000"))
EMBED = os.environ.get("GEMINI_EMBED", "gemini-embedding-001")

app = FastAPI()


def db():
    c = sqlite3.connect(DB)
    c.execute("create table if not exists caps (id text primary key, data text, created text default current_timestamp)")
    cols = [r[1] for r in c.execute("pragma table_info(caps)")]
    if "emb" not in cols:
        c.execute("alter table caps add column emb text")
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
 "glossary": [{"term": "", "means": ""}]
}"""

EXTRACT = """You compress a dying AI chat session into a transferable context capsule.

The next assistant will read only your capsule, never this transcript. Capture what is
expensive to rediscover: decisions and the reasoning behind them, approaches already ruled
out, constraints the user imposed, and exactly where the work stands.

Drop pleasantries, restated code the user already has, and anything the next assistant can
re-derive in one step.

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


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def blank(c):
    d = {"title": "", "goal": "", "state": "", "decisions": [], "rejected": [], "constraints": [],
         "artifacts": [], "open_threads": [], "next_action": "", "glossary": []}
    d.update({k: v for k, v in c.items() if k in d and v})
    return d


def render(c, target, budget):
    c = blank(c)
    order = ["goal", "state", "next_action", "decisions", "constraints", "rejected",
             "open_threads", "artifacts", "glossary"]
    if budget <= 600:
        order = order[:4]
    elif budget <= 2200:
        order = order[:7]

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
             "rejected": "Approaches already ruled out", "open_threads": "Still unresolved",
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


@app.post("/api/capsule")
def make(i: In):
    t = i.transcript.strip()
    if len(t) < 80:
        raise HTTPException(400, "Paste more of the conversation. At least a few exchanges.")
    model = route(t)
    cap = blank(gemini(EXTRACT + t[:120000], model))
    cid = secrets.token_urlsafe(6)
    emb = embed(json.dumps(cap))
    c = db()
    c.execute("insert into caps (id, data, emb) values (?, ?, ?)", (cid, json.dumps(cap), json.dumps(emb) if emb else None))
    c.commit()
    c.close()
    return {"id": cid, "capsule": cap, "model": model}


def load(cid):
    c = db()
    r = c.execute("select data from caps where id=?", (cid,)).fetchone()
    c.close()
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


@app.get("/api/search")
def search(q: str):
    qe = embed(q.strip())
    if not qe:
        raise HTTPException(502, "Embedding call failed")
    c = db()
    rows = c.execute("select id, data, emb from caps where emb is not null").fetchall()
    c.close()
    # ponytail: linear scan over sqlite rows, move to a vector index past a few thousand capsules
    hits = []
    for cid, data, emb in rows:
        cap = json.loads(data)
        hits.append({"id": cid, "title": cap.get("title", ""), "goal": cap.get("goal", ""), "score": round(cosine(qe, json.loads(emb)), 3)})
    hits.sort(key=lambda h: -h["score"])
    return {"hits": hits[:5]}


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
