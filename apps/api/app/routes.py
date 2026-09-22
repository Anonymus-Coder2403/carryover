import json
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from .capsules import make_capsule, load, render, search_caps
from .config import KEY, PUBLIC_API_URL, SUPABASE_URL
from .db import Session
from .gemini import gemini, VERIFY
from .models import Capsule

router = APIRouter()

PAGE = open(os.path.join(os.path.dirname(__file__), "index.html")).read()


class In(BaseModel):
    transcript: str
    parent: str | None = None


@router.post("/api/capsule")
def make(i: In):
    return make_capsule(i.transcript, None, i.parent)


@router.get("/api/capsule/{cid}")
def get(cid: str):
    with Session() as s:
        row = s.get(Capsule, cid)
    return {"id": cid, "capsule": load(cid), "parent": row.parent if row else None}


@router.get("/api/resume/{cid}", response_class=PlainTextResponse)
def resume(cid: str, target: str = "claude", budget: int = 2000):
    if target not in ("claude", "chatgpt", "cursor"):
        raise HTTPException(400, "target must be claude, chatgpt or cursor")
    return render(load(cid), target, budget)


@router.post("/api/verify/{cid}")
def verify(cid: str, i: In):
    cap = load(cid)
    out = gemini(VERIFY % (i.transcript.strip()[:120000], json.dumps(cap)))
    checks = [c for c in out.get("checks", []) if isinstance(c, dict)][:3]
    return {"checks": checks, "verdict": out.get("verdict", ""),
            "passed": sum(1 for c in checks if c.get("preserved")), "total": len(checks)}


@router.get("/api/search")
def search(q: str):
    return search_caps(q)


@router.get("/healthz")
def health():
    return {"ok": True, "key": bool(KEY)}


@router.get("/.well-known/oauth-protected-resource")
def protected_resource():
    return {"resource": PUBLIC_API_URL + "/mcp", "authorization_servers": [SUPABASE_URL + "/auth/v1"]}


@router.get("/", response_class=HTMLResponse)
def home():
    return PAGE


@router.get("/c/{cid}", response_class=HTMLResponse)
def shared(cid: str):
    load(cid)
    return PAGE.replace("__PRELOAD__", cid)
