import json
import re
import urllib.request
import urllib.error

from fastapi import HTTPException

from .config import KEY, MODEL, LITE, ROUTE_AT, EMBED

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

CHAIN = """

PRIOR CAPSULE from the session before this one. Carry forward every decision, ruled out
approach, constraint and literal from it unless this transcript explicitly reverses it. The
new capsule must stand alone: someone reading only it must know everything from both.

"""

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
