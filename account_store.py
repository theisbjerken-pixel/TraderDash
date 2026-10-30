"""Server-side account storage.

The Streamlit pages call accounts.py. SQL stays in this module.

Local development uses SQLite. Supabase Postgres is used when DATABASE_URL
is set, and whenever the app is running on Streamlit Community Cloud.
A failed Postgres connection is not replaced with a local database file.

Stripe subscription fields stay on the user row. One account has one plan,
so a separate subscriptions table would be a second copy of the same facts.
"""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit

PLANS = ("free", "nordic", "international")
SUBSCRIPTION_STATUSES = (
    "free",
    "active",
    "trialing",
    "past_due",
    "incomplete",
    "cancelled",
    "expired",
)
EVENT_STATUSES = ("received", "rejected", "failed")

SAFE_DB_MESSAGE = (
    "TraderDash kan ikke åbne den delte database. "
    "Kontrollér opsætningen, og prøv igen."
)
SCHEMA_MESSAGE = (
    "TraderDash kan ikke læse kontotabellerne i den delte database. "
    "Kør database-migreringen, og prøv igen."
)

_USER_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_USER_COLUMNS = """
    user_id, email, plan, subscription_status, stripe_customer_id,
    stripe_subscription_id, subscription_current_period_end,
    cancel_at_period_end, created_at, updated_at
"""


class AccountError(Exception):
    """A rejected account change that is safe to explain to the user."""


class AccountConfigError(Exception):
    """The shared database is missing or unreachable. The message is safe to show."""


@dataclass(frozen=True)
class User:
    user_id: str
    email: str
    plan: str
    subscription_status: str
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    created_at: str
    updated_at: str
    subscription_current_period_end: str | None = None
    cancel_at_period_end: bool = False


@dataclass(frozen=True)
class Subscription:
    user_id: str
    plan: str
    status: str
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    current_period_end: str | None
    cancel_at_period_end: bool


class _Connection:
    def __init__(self, raw: object, kind: str) -> None:
        self.raw = raw
        self.kind = kind

    def execute(self, sql: str, params: tuple = ()):
        if self.kind == "postgres":
            sql = sql.replace("?", "%s")
        return self.raw.execute(sql, params)

    def commit(self) -> None:
        self.raw.commit()

    def close(self) -> None:
        self.raw.close()


def storage_backend(database: Path | None = None) -> str:
    """Return sqlite or postgres without opening a connection."""
    kind, _target = _select_backend(database)
    return kind


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sqlite_path() -> Path:
    configured = os.environ.get("TRADERDASH_DATABASE", "").strip()
    if not configured:
        configured = _secret("database_path")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / "data" / "traderdash.db"


def insert_user(
    user: User,
    password_hash: str,
    *,
    database: Path | None = None,
) -> None:
    with _connection(database) as connection:
        try:
            connection.execute(
                f"""
                INSERT INTO users (
                    user_id, email, password_hash, plan, subscription_status,
                    stripe_customer_id, stripe_subscription_id,
                    subscription_current_period_end, cancel_at_period_end,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, {_false_sql(connection)}, ?, ?)
                """,
                (
                    user.user_id,
                    user.email,
                    password_hash,
                    user.plan,
                    user.subscription_status,
                    user.created_at,
                    user.updated_at,
                ),
            )
            connection.commit()
        except Exception as exc:
            if _is_integrity_error(exc):
                raise AccountError("Der findes allerede en konto med den e-mail.") from exc
            raise


def get_user_by_id(user_id: str, *, database: Path | None = None) -> User | None:
    if not user_id:
        kind, target = _select_backend(database)
        if kind == "postgres":
            _open_postgres(str(target)).close()
        return None
    with _connection(database) as connection:
        row = connection.execute(
            f"SELECT {_USER_COLUMNS} FROM users WHERE user_id = ?",
            (str(user_id),),
        ).fetchone()
    if row is None:
        return None
    return _user_from_row(row)


def get_user_by_email(email: str, *, database: Path | None = None) -> User | None:
    address = str(email or "").strip().lower()
    if not address:
        return None
    with _connection(database) as connection:
        row = connection.execute(
            f"SELECT {_USER_COLUMNS} FROM users WHERE email = ?",
            (address,),
        ).fetchone()
    if row is None:
        return None
    return _user_from_row(row)


def password_hash_for_email(email: str, *, database: Path | None = None) -> str | None:
    address = str(email or "").strip().lower()
    if not address:
        return None
    with _connection(database) as connection:
        row = connection.execute(
            "SELECT password_hash FROM users WHERE email = ?",
            (address,),
        ).fetchone()
    if row is None:
        return None
    return str(row["password_hash"])


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
    """Trusted server write. The Account page does not call this."""
    if plan not in PLANS:
        raise AccountError("Ukendt plan.")
    if subscription_status not in SUBSCRIPTION_STATUSES:
        raise AccountError("Ukendt abonnementsstatus.")
    if not isinstance(cancel_at_period_end, bool):
        raise AccountError("Ugyldig opsigelsesmarkering.")
    customer_id = _clean_token(stripe_customer_id)
    subscription_id = _clean_token(stripe_subscription_id)
    period_end = _clean_period(subscription_current_period_end)
    if not user_id:
        raise AccountError("Kontoen blev ikke fundet.")

    with _connection(database) as connection:
        try:
            cursor = connection.execute(
                f"""
                UPDATE users
                SET plan = ?, subscription_status = ?, stripe_customer_id = ?,
                    stripe_subscription_id = ?, subscription_current_period_end = ?,
                    cancel_at_period_end = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (
                    plan,
                    subscription_status,
                    customer_id,
                    subscription_id,
                    period_end,
                    _store_bool(connection, cancel_at_period_end),
                    utc_now(),
                    str(user_id),
                ),
            )
            if cursor.rowcount == 0:
                raise AccountError("Kontoen blev ikke fundet.")
            connection.commit()
        except AccountError:
            raise
        except Exception as exc:
            if _is_integrity_error(exc):
                raise AccountError("Stripe-kunden er allerede knyttet til en anden konto.") from exc
            raise
    user = get_user_by_id(user_id, database=database)
    if user is None:
        raise AccountError("Kontoen blev ikke fundet.")
    return user


def get_subscription_for_user(user_id: str, *, database: Path | None = None) -> Subscription | None:
    user = get_user_by_id(user_id, database=database)
    if user is None:
        return None
    return Subscription(
        user_id=user.user_id,
        plan=user.plan,
        status=user.subscription_status,
        stripe_customer_id=user.stripe_customer_id,
        stripe_subscription_id=user.stripe_subscription_id,
        current_period_end=user.subscription_current_period_end,
        cancel_at_period_end=user.cancel_at_period_end,
    )


def record_stripe_event(
    stripe_event_id: str,
    event_type: str,
    *,
    processing_status: str = "received",
    error_message: str | None = None,
    database: Path | None = None,
) -> bool:
    """Insert one event. A repeated id returns False and does not change the row."""
    event_id = _clean_token(stripe_event_id)
    kind = str(event_type or "").strip()
    if not event_id or not kind or len(kind) > 120:
        raise AccountError("Ugyldigt Stripe-hændelses-id.")
    if processing_status not in EVENT_STATUSES:
        raise AccountError("Ugyldig hændelsesstatus.")
    message = str(error_message).strip() if error_message else None
    if message:
        message = message[:500]
    with _connection(database) as connection:
        try:
            connection.execute(
                """
                INSERT INTO stripe_events (
                    stripe_event_id, event_type, processed_at, processing_status, error_message
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, kind, utc_now(), processing_status, message),
            )
            connection.commit()
        except Exception as exc:
            if _is_integrity_error(exc):
                return False
            raise
    return True


def stripe_event_already_processed(stripe_event_id: str, *, database: Path | None = None) -> bool:
    event_id = _clean_token(stripe_event_id)
    if not event_id:
        return False
    with _connection(database) as connection:
        row = connection.execute(
            "SELECT stripe_event_id FROM stripe_events WHERE stripe_event_id = ?",
            (event_id,),
        ).fetchone()
    return row is not None


def traderdash_user_id_from_stripe_event(payload: dict) -> str | None:
    """Internal user id from Checkout metadata. Email is never accepted."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    if not isinstance(obj, dict):
        return None
    reference = obj.get("client_reference_id")
    metadata = obj.get("metadata")
    from_metadata = metadata.get("user_id") if isinstance(metadata, dict) else None
    candidate = reference if isinstance(reference, str) and reference else from_metadata
    if not isinstance(candidate, str) or not _USER_ID.fullmatch(candidate):
        return None
    return candidate


def running_on_streamlit_cloud() -> bool:
    cwd = Path.cwd().as_posix()
    if cwd == "/mount/src" or cwd.startswith("/mount/src/"):
        return True
    return os.environ.get("USER", "") == "appuser"


@contextmanager
def _connection(database: Path | None) -> Iterator[_Connection]:
    kind, target = _select_backend(database)
    if kind == "sqlite":
        raw = _open_sqlite(Path(target))
    else:
        raw = _open_postgres(str(target))
    connection = _Connection(raw, kind)
    try:
        yield connection
    finally:
        connection.close()


def _select_backend(database: Path | None) -> tuple[str, Path | str]:
    if database is not None:
        return ("sqlite", database)
    environment = _setting("TRADERDASH_ENV", "environment").lower()
    database_url = _setting("DATABASE_URL", "database_url")
    if running_on_streamlit_cloud() or environment == "production":
        if not database_url:
            raise AccountConfigError(SAFE_DB_MESSAGE)
        return ("postgres", database_url)
    if environment == "local":
        return ("sqlite", sqlite_path())
    if database_url:
        return ("postgres", database_url)
    return ("sqlite", sqlite_path())


def _open_sqlite(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    _ensure_sqlite(connection)
    return connection


def _ensure_sqlite(connection: sqlite3.Connection) -> None:
    info = list(connection.execute("PRAGMA table_info(users)"))
    if not info:
        connection.execute(
            """
            CREATE TABLE users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                plan TEXT NOT NULL CHECK (plan IN ('free', 'nordic', 'international')),
                subscription_status TEXT NOT NULL CHECK (
                    subscription_status IN (
                        'free', 'active', 'trialing', 'past_due',
                        'incomplete', 'cancelled', 'expired'
                    )
                ),
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                subscription_current_period_end TEXT,
                cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
    else:
        names = {row[1] for row in info}
        if "subscription_current_period_end" not in names:
            connection.execute("ALTER TABLE users ADD COLUMN subscription_current_period_end TEXT")
        if "cancel_at_period_end" not in names:
            connection.execute(
                "ALTER TABLE users ADD COLUMN cancel_at_period_end INTEGER NOT NULL DEFAULT 0"
            )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS stripe_events (
            stripe_event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            processed_at TEXT NOT NULL,
            processing_status TEXT NOT NULL CHECK (
                processing_status IN ('received', 'rejected', 'failed')
            ),
            error_message TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS users_stripe_customer_id_key
        ON users (stripe_customer_id)
        WHERE stripe_customer_id IS NOT NULL
        """
    )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS users_stripe_subscription_id_key
        ON users (stripe_subscription_id)
        WHERE stripe_subscription_id IS NOT NULL
        """
    )
    connection.commit()


def _open_postgres(url: str):
    scheme = urlsplit(url).scheme
    if scheme not in {"postgres", "postgresql"}:
        raise AccountConfigError(SAFE_DB_MESSAGE)
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise AccountConfigError(SAFE_DB_MESSAGE) from exc
    host = (urlsplit(url).hostname or "").lower()
    kwargs = {
        "connect_timeout": 8,
        "row_factory": dict_row,
        "application_name": "traderdash",
    }
    if host not in {"localhost", "127.0.0.1", "::1"}:
        kwargs["sslmode"] = "require"
    try:
        connection = psycopg.connect(url, **kwargs)
    except Exception as exc:
        raise AccountConfigError(SAFE_DB_MESSAGE) from exc
    try:
        connection.execute("SELECT user_id FROM users LIMIT 0")
        connection.execute("SELECT stripe_event_id FROM stripe_events LIMIT 0")
        connection.rollback()
    except Exception as exc:
        connection.close()
        raise AccountConfigError(SCHEMA_MESSAGE) from exc
    return connection


def _user_from_row(row) -> User:
    return User(
        user_id=row["user_id"],
        email=row["email"],
        plan=row["plan"],
        subscription_status=row["subscription_status"],
        stripe_customer_id=row["stripe_customer_id"],
        stripe_subscription_id=row["stripe_subscription_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        subscription_current_period_end=row["subscription_current_period_end"],
        cancel_at_period_end=_as_bool(row["cancel_at_period_end"]),
    )


def _false_sql(connection: _Connection) -> str:
    if connection.kind == "postgres":
        return "FALSE"
    return "0"


def _store_bool(connection: _Connection, value: bool):
    if connection.kind == "postgres":
        return value
    return 1 if value else 0


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes"}
    return False


def _clean_token(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > 255:
        raise AccountError("Værdien er for lang.")
    return text


def _clean_period(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > 40:
        raise AccountError("Periodens sluttidspunkt er ugyldigt.")
    return text


def _is_integrity_error(exc: Exception) -> bool:
    if isinstance(exc, sqlite3.IntegrityError):
        return True
    return exc.__class__.__name__ in {"IntegrityError", "UniqueViolation"}


def _setting(env_name: str, secret_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if value:
        return value
    return _secret(secret_name)


def _secret(key: str) -> str:
    try:
        import streamlit as st

        value = st.secrets.get(key, "")
    except Exception:
        return ""
    return str(value).strip() if value else ""
