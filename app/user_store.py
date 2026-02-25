"""User store: email -> hashed password. Uses Supabase when configured, else in-memory."""

from typing import List

from passlib.context import CryptContext

from app.db import get_supabase, use_supabase

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
_users: dict[str, str] = {}  # email (lower) -> hashed password (in-memory fallback)

# Bcrypt (pyca/bcrypt 5.0+) raises if password > 72 bytes; truncate before hashing
BCRYPT_MAX_BYTES = 72


def _password_bytes_for_bcrypt(password: str) -> bytes:
    """Truncate password to 72 bytes (UTF-8) for bcrypt. Pass bytes so backend gets exact length."""
    pwd_bytes = password.encode("utf-8")
    return pwd_bytes[:BCRYPT_MAX_BYTES]


def register(email: str, password: str) -> bool:
    """Register a user. Returns True if created, False if email already exists."""
    key = email.strip().lower()
    pwd = _password_bytes_for_bcrypt(password)
    if use_supabase():
        sb = get_supabase()
        existing = sb.table("users").select("email").eq("email", key).execute()
        if existing.data and len(existing.data) > 0:
            return False
        sb.table("users").insert({
            "email": key,
            "password_hash": _ctx.hash(pwd),
        }).execute()
        return True
    if key in _users:
        return False
    _users[key] = _ctx.hash(pwd)
    return True


def verify(email: str, password: str) -> bool:
    """Verify email and password. Returns True if valid."""
    key = email.strip().lower()
    pwd = _password_bytes_for_bcrypt(password)
    if use_supabase():
        sb = get_supabase()
        res = sb.table("users").select("password_hash").eq("email", key).execute()
        if not res.data or len(res.data) == 0:
            return False
        return _ctx.verify(pwd, res.data[0]["password_hash"])
    hashed = _users.get(key)
    if not hashed:
        return False
    return _ctx.verify(pwd, hashed)


def list_all() -> List[str]:
    """List all user emails (for superuser admin)."""
    if use_supabase():
        sb = get_supabase()
        res = sb.table("users").select("email").order("email").execute()
        return [row["email"] for row in (res.data or [])]
    return sorted(_users.keys())


def delete_user(email: str) -> bool:
    """Delete a user by email. Returns True if the user existed and was removed. Also removes their sessions."""
    key = email.strip().lower()
    if use_supabase():
        sb = get_supabase()
        sb.table("sessions").delete().eq("customer_email", key).execute()
        res = sb.table("users").delete().eq("email", key).execute()
        return res.data is not None and len(res.data) > 0
    if key in _users:
        del _users[key]
        return True
    return False
