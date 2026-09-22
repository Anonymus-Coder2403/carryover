import os

DATABASE_URL = os.environ["DATABASE_URL"]
SUPABASE_URL = os.environ["SUPABASE_URL"]
PUBLIC_API_URL = os.environ["PUBLIC_API_URL"]

KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
LITE = os.environ.get("GEMINI_LITE", "gemini-3.1-flash-lite")
ROUTE_AT = int(os.environ.get("ROUTE_AT", "0"))
EMBED = os.environ.get("GEMINI_EMBED", "gemini-embedding-001")
