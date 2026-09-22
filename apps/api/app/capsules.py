import json
import re
import secrets

from fastapi import HTTPException

from .db import Session
from .models import Capsule
from .gemini import gemini, embed, route, EXTRACT, CHAIN


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


def make_capsule(transcript, owner=None, parent=None):
    t = transcript.strip()
    if len(t) < 80:
        raise HTTPException(400, "Paste more of the conversation. At least a few exchanges.")
    prior = load(parent, owner) if parent else None
    model = route(t)
    prompt = EXTRACT + t[:120000] + (CHAIN + json.dumps(prior) if prior else "")
    cap = blank(gemini(prompt, model))
    # ponytail: regex backstop because models drop long encoded urls, capped at 40 to bound prompt size
    seen = set(cap["literals"])
    for u in dict.fromkeys(re.findall(r"https?://[^\s\"'<>)\]]+", t[:120000])):
        if u not in seen and len(cap["literals"]) < 40:
            cap["literals"].append(u)
    cid = secrets.token_urlsafe(6)
    emb = embed(json.dumps(cap))
    with Session() as s:
        s.add(Capsule(id=cid, data=cap, emb=emb, owner=owner, parent=parent if prior else None))
        s.commit()
    return {"id": cid, "capsule": cap, "model": model, "parent": parent if prior else None}


def load(cid, owner=None):
    with Session() as s:
        row = s.get(Capsule, cid)
    if row and row.owner and row.owner != owner:
        row = None
    if not row:
        raise HTTPException(404, "No capsule with that id. It may have expired on a redeploy.")
    return row.data


def search_caps(q, owner=None):
    qe = embed(q.strip())
    if not qe:
        raise HTTPException(502, "Embedding call failed")
    owner_match = Capsule.owner.is_(None) if owner is None else Capsule.owner == owner
    with Session() as s:
        rows = s.query(Capsule).filter(Capsule.emb.isnot(None), owner_match).all()
    # ponytail: linear scan over db rows, move to a vector index past a few thousand capsules
    hits = []
    for row in rows:
        hits.append({"id": row.id, "title": row.data.get("title", ""), "goal": row.data.get("goal", ""),
                     "score": round(cosine(qe, row.emb), 3)})
    hits.sort(key=lambda h: -h["score"])
    return {"hits": hits[:5]}
