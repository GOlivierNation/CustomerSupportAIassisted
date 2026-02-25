import os

from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-4o-mini")

# Supabase (optional: leave empty to use in-memory stores)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Superuser: comma-separated emails allowed to access /admin
SUPERUSER_EMAILS = {
    e.strip().lower()
    for e in os.getenv("SUPERUSER_EMAILS", "").split(",")
    if e.strip()
}

# Optional: on startup, create any superuser account that doesn't exist yet (so you can log in as admin immediately)
ADMIN_BOOTSTRAP_PASSWORD = os.getenv("ADMIN_BOOTSTRAP_PASSWORD", "").strip() or None

# Optional: contact email shown when AI is not configured (e.g. support@company.com). If unset, uses customer email.
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "").strip() or None
