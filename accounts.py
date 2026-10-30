"""Persistent TraderDash accounts.

Stock lists, scores and market data do not live here. The only value the
rest of the app needs from an account is its stored plan.

Passwords are stored as scrypt hashes. Local development uses SQLite.
Supabase Postgres is used when DATABASE_URL is configured. Pages never
query the database themselves, and they never receive the service-role key.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import threading
import uuid
from pathlib import Path

import account_store
from account_store import (
    PLANS,
    SUBSCRIPTION_STATUSES,
    AccountConfigError,
    AccountError,
    Subscription,
    User,
)

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_LOCK = threading.Lock()
_DUMMY_HASH: str | None = None


def database_file() -> Path:
    """Local SQLite path. Production does not use this file."""
    return account_store.sqlite_path()


def developer_override_enabled() -> bool:
    return os.environ.get("TRADERDASH_DEV_OVERRIDE", "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_plan(stored_plan: str, session_choice: str | None = None) -> str:
    """Plan used for this request.

    The stored account plan wins. A session value is ignored unless the
    developer override is turned on with TRADERDASH_DEV_OVERRIDE.
    """
    stored = stored_plan if stored_plan in PLANS else "free"
    if not developer_override_enabled():
        return stored
    if session_choice in PLANS:
        return session_choice
    chosen = os.environ.get("TRADERDASH_DEV_PLAN", "").strip().lower()
    if chosen in PLANS:
        return chosen
    return stored


def create_user(email: str, password: str, *, database: Path | None = None) -> User:
    address = _normalize_email(email)
    _validate_password(password)
    now = account_store.utc_now()
    user = User(
        user_id=_new_user_id(),
        email=address,
        plan="free",
        subscription_status="free",
        stripe_customer_id=None,
        stripe_subscription_id=None,
        created_at=now,
        updated_at=now,
    )
    with _LOCK:
        account_store.insert_user(user, _hash_password(password), database=database)
    return user


def authenticate(email: str, password: str, *, database: Path | None = None) -> User | None:
    address = str(email or "").strip().lower()
    with _LOCK:
        stored = account_store.password_hash_for_email(address, database=database)
    if stored is None:
        _verify_password(password, _dummy_hash())
        return None
    if not _verify_password(password, stored):
        return None
    return get_user_by_email(address, database=database)


def get_user(user_id: str, *, database: Path | None = None) -> User | None:
    return get_user_by_id(user_id, database=database)


def get_user_by_id(user_id: str, *, database: Path | None = None) -> User | None:
    with _LOCK:
        return account_store.get_user_by_id(user_id, database=database)


def get_user_by_email(email: str, *, database: Path | None = None) -> User | None:
    with _LOCK:
        return account_store.get_user_by_email(email, database=database)


def update_user_subscription(
    user_id: str,
    *,
    plan: str,
    subscription_status: str,
    stripe_customer_id: str | None,
    stripe_subscription_id: str | None,
    subscription_current_period_end: str | None,
    cancel_at_period_end: bool,
    database: Path | None = None,
) -> User:
    """Trusted server write. Normal users have no call path to this function."""
    with _LOCK:
        return account_store.update_user_subscription(
            user_id,
            plan=plan,
            subscription_status=subscription_status,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            subscription_current_period_end=subscription_current_period_end,
            cancel_at_period_end=cancel_at_period_end,
            database=database,
        )


def get_subscription_for_user(user_id: str, *, database: Path | None = None) -> Subscription | None:
    with _LOCK:
        return account_store.get_subscription_for_user(user_id, database=database)


def record_stripe_event(
    stripe_event_id: str,
    event_type: str,
    *,
    processing_status: str = "received",
    error_message: str | None = None,
    database: Path | None = None,
) -> bool:
    with _LOCK:
        return account_store.record_stripe_event(
            stripe_event_id,
            event_type,
            processing_status=processing_status,
            error_message=error_message,
            database=database,
        )


def stripe_event_already_processed(stripe_event_id: str, *, database: Path | None = None) -> bool:
    with _LOCK:
        return account_store.stripe_event_already_processed(stripe_event_id, database=database)


def _new_user_id() -> str:
    return str(uuid.uuid4())


def _normalize_email(email: str) -> str:
    address = str(email or "").strip().lower()
    if not _EMAIL.fullmatch(address) or len(address) > 254:
        raise AccountError("Skriv en gyldig e-mail.")
    return address


def _validate_password(password: str) -> None:
    if not isinstance(password, str) or len(password) < 10 or len(password) > 128:
        raise AccountError("Adgangskoden skal være mindst 10 tegn.")


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=32,
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, n_text, r_text, p_text, salt_hex, digest_hex = stored.split("$")
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(
            str(password or "").encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n_text),
            r=int(r_text),
            p=int(p_text),
            dklen=32,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, bytes.fromhex(digest_hex))


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = _hash_password("not-a-real-password")
    return _DUMMY_HASH
