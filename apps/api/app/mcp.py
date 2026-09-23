import json

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from .auth import owner_of
from .capsules import make_capsule, load, render, search_caps
from .config import PUBLIC_API_URL

router = APIRouter()

TOOLS = [
    {"name": "save_capsule",
     "description": "Compress a chat transcript into a private context capsule owned by this connector. Returns the capsule id and the capsule itself. The transcript is never stored.",
     "inputSchema": {"type": "object", "properties": {
         "transcript": {"type": "string", "description": "The full chat, both sides"},
         "parent": {"type": "string", "description": "Optional id of the previous capsule in this line of work. The new capsule carries its decisions forward."}}, "required": ["transcript"]}},
    {"name": "load_capsule",
     "description": "Load a saved capsule as a resume prompt by id, or search saved capsules by meaning with a query. Give one of id or query.",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "string", "description": "Capsule id from save_capsule"},
         "query": {"type": "string", "description": "What the work was about, used for search when id is not known"},
         "target": {"type": "string", "enum": ["claude", "chatgpt", "cursor"], "description": "Prompt dialect, default claude"}}}},
]


def tool(name, a, owner):
    if name == "save_capsule":
        r = make_capsule(a.get("transcript", ""), owner, a.get("parent"))
        return json.dumps({"id": r["id"], "parent": r["parent"], "model": r["model"], "private": True, "capsule": r["capsule"]}, indent=1)
    if name == "load_capsule":
        if a.get("id"):
            return render(load(a["id"], owner), a.get("target", "claude"), 2000)
        if a.get("query"):
            return json.dumps(search_caps(a["query"], owner), indent=1)
        raise HTTPException(400, "Give an id or a query")
    raise HTTPException(404, "Unknown tool: %s" % name)


@router.post("/mcp")
async def mcp(req: Request):
    owner = owner_of(req)
    if not owner:
        resource_metadata = PUBLIC_API_URL + "/.well-known/oauth-protected-resource"
        www_auth = 'Bearer resource_metadata="%s"' % resource_metadata
        return JSONResponse({"jsonrpc": "2.0", "error": {"code": -32001, "message": "Unauthorized. Send Authorization: Bearer <supabase access token>."}, "id": None},
                            401, headers={"WWW-Authenticate": www_auth})
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


@router.get("/mcp")
def mcp_get():
    return Response(status_code=405)
