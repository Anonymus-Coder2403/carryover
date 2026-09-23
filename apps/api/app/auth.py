import jwt
from jwt import PyJWKClient

from .config import SUPABASE_URL

# Supabase signs with per-project asymmetric keys (ES256/RS256) now, not a shared secret,
# verified against the project's own published public keys. cache_keys avoids a network
# call on every request, jwks_client refreshes if a kid it hasn't seen shows up.
_jwks_client = PyJWKClient(SUPABASE_URL + "/auth/v1/.well-known/jwks.json", cache_keys=True)


class PathToken:
    """Accepts /mcp/<token> for clients that cannot send headers, and hides the token from access logs."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"].startswith("/mcp/"):
            scope["path_token"] = scope["path"][5:].strip("/")
            scope["path"] = "/mcp"
            scope["raw_path"] = b"/mcp"
        await self.app(scope, receive, send)


def verify_jwt(token):
    # aud is "authenticated" for password/magic link tokens but may be a client_id for
    # OAuth issued ones (claude.ai's connector), so signature and expiry are what we trust
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(token, signing_key.key, algorithms=["ES256", "RS256"], options={"verify_aud": False})
    except jwt.PyJWTError:
        return None
    return claims.get("sub")


def owner_of(req):
    auth = req.headers.get("authorization", "")
    tok = auth[7:].strip() if auth.lower().startswith("bearer ") else req.scope.get("path_token", "")
    if not tok:
        return None
    return verify_jwt(tok)
