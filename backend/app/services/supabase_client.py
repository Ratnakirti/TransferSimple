"""
Supabase client — database queries and storage bucket access.
"""
import asyncio
import logging
from typing import Optional

from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY, BUCKET_NAME

log = logging.getLogger(__name__)

# Timeouts (seconds) to prevent Supabase calls from hanging when the
# corporate proxy is unreachable or the network is slow.
_PING_TIMEOUT       = 5.0
_QUERY_TIMEOUT      = 10.0
_DOWNLOAD_TIMEOUT   = 20.0
_AUDIT_TIMEOUT      = 10.0


def _make_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in backend/.env"
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# Module-level singleton
_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = _make_client()
    return _client


# ── Customer queries ──────────────────────────────────────────────────

def _sync_get_customer(ws_account_num: str) -> Optional[dict]:
    """Fetch a single customer row by Wealthsimple account number."""
    response = (
        get_client()
        .table("customers")
        .select("*")
        .eq("ws_account_num", ws_account_num)
        .limit(1)
        .execute()
    )
    rows = response.data
    return rows[0] if rows else None


async def get_customer_by_ws_account(ws_account_num: str) -> Optional[dict]:
    """Async wrapper — runs the synchronous Supabase call in a thread pool."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_sync_get_customer, ws_account_num),
            timeout=_QUERY_TIMEOUT,
        )
    except (asyncio.TimeoutError, Exception) as exc:
        log.warning("get_customer_by_ws_account timed out or failed: %s", exc)
        return None


# ── Connectivity check ────────────────────────────────────────────────

def _sync_ping() -> bool:
    """Quick ping — fetch a single row from customers (or empty result is fine)."""
    try:
        get_client().table("customers").select("sin").limit(1).execute()
        return True
    except Exception:
        return False


async def ping() -> bool:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_sync_ping),
            timeout=_PING_TIMEOUT,
        )
    except (asyncio.TimeoutError, Exception) as exc:
        log.warning("Supabase ping timed out or failed: %s", exc)
        return False


# ── Storage bucket ────────────────────────────────────────────────────

def _sync_download_file(filename: str) -> bytes:
    """Download a file from the clearinghouse-resources bucket."""
    response = get_client().storage.from_(BUCKET_NAME).download(filename)
    return response  # supabase-py returns bytes directly


async def download_sim_file(filename: str) -> bytes:
    """Async wrapper for bucket file download."""
    return await asyncio.wait_for(
        asyncio.to_thread(_sync_download_file, filename),
        timeout=_DOWNLOAD_TIMEOUT,
    )


# ── Audit log ─────────────────────────────────────────────────────────

def _sync_log_audit(record: dict) -> None:
    get_client().table("transfer_audit").insert(record).execute()


async def log_audit(record: dict) -> None:
    """Append an audit entry to the transfer_audit table."""
    try:
        await asyncio.wait_for(
            asyncio.to_thread(_sync_log_audit, record),
            timeout=_AUDIT_TIMEOUT,
        )
    except (asyncio.TimeoutError, Exception) as exc:
        log.warning("log_audit timed out or failed: %s", exc)
