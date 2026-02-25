"""Supabase client. Uses in-memory fallback when SUPABASE_URL is not set."""

from typing import Optional

from app.config import SUPABASE_KEY, SUPABASE_URL

_supabase_client: Optional[object] = None


def get_supabase():
    """Return Supabase client or None if not configured."""
    global _supabase_client
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    if _supabase_client is None:
        from supabase import create_client
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


def use_supabase() -> bool:
    """Return True if Supabase is configured and should be used."""
    return bool(SUPABASE_URL and SUPABASE_KEY)
