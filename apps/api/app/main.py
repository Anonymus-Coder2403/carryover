from fastapi import FastAPI

from .auth import PathToken
from .db import init_db
from .mcp import router as mcp_router
from .routes import router as web_router

app = FastAPI()
app.add_middleware(PathToken)
app.include_router(web_router)
app.include_router(mcp_router)


@app.on_event("startup")
def startup():
    init_db()
