"""Local checks for the shared account store.

Supabase itself is reached only when DATABASE_URL is configured. These tests
use a temporary SQLite file, and they check that a broken production URL
does not create that file.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import accounts
import account_store
from account_store import SAFE_DB_MESSAGE, AccountConfigError, AccountError

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "correct-horse"


@contextmanager
def scoped_env(**values):
    previous = {key: os.environ.get(key) for key in values}
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class AccountStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = Path(tempfile.mkdtemp())
        cls.database = cls.directory / "local.db"
        with scoped_env(
            TRADERDASH_ENV="local",
            DATABASE_URL=None,
            TRADERDASH_DATABASE=str(cls.database),
            TRADERDASH_DEV_OVERRIDE=None,
        ):
            cls.user = accounts.create_user("owner@example.com", PASSWORD)

    def setUp(self):
        self._previous = {
            key: os.environ.get(key)
            for key in ("TRADERDASH_ENV", "DATABASE_URL", "TRADERDASH_DATABASE", "TRADERDASH_DEV_OVERRIDE")
        }
        os.environ["TRADERDASH_ENV"] = "local"
        os.environ["TRADERDASH_DATABASE"] = str(self.database)
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("TRADERDASH_DEV_OVERRIDE", None)

    def tearDown(self):
        for key, value in self._previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_explicit_local_mode_uses_sqlite(self):
        self.assertEqual(account_store.storage_backend(), "sqlite")
        self.assertTrue(self.database.exists())
        self.assertEqual(self.user.plan, "free")
        self.assertEqual(self.user.subscription_status, "free")
        self.assertFalse(self.user.cancel_at_period_end)

    def test_local_mode_ignores_a_database_url(self):
        with scoped_env(DATABASE_URL="postgresql://traderdash:supersecret@127.0.0.1:1/nope"):
            self.assertEqual(account_store.storage_backend(), "sqlite")
            user = accounts.get_user(self.user.user_id)
        self.assertEqual(user.email, "owner@example.com")

    def test_production_configuration_selects_postgres(self):
        with scoped_env(TRADERDASH_ENV="production", DATABASE_URL="postgresql://example/traderdash"):
            self.assertEqual(account_store.storage_backend(), "postgres")

    def test_production_connection_failure_does_not_create_sqlite(self):
        sentinel = self.directory / "must-not-exist.db"
        with scoped_env(
            TRADERDASH_ENV="production",
            DATABASE_URL="postgresql://traderdash:supersecret@127.0.0.1:1/nope",
            TRADERDASH_DATABASE=str(sentinel),
        ):
            with self.assertRaises(AccountConfigError) as caught:
                accounts.get_user("")
        self.assertEqual(str(caught.exception), SAFE_DB_MESSAGE)
        self.assertNotIn("supersecret", str(caught.exception))
        self.assertFalse(sentinel.exists())

    def test_production_without_url_does_not_create_sqlite(self):
        sentinel = self.directory / "missing-url.db"
        with scoped_env(TRADERDASH_ENV="production", DATABASE_URL=None, TRADERDASH_DATABASE=str(sentinel)):
            with self.assertRaises(AccountConfigError):
                accounts.get_user("")
        self.assertFalse(sentinel.exists())

    def test_streamlit_cloud_without_url_does_not_create_sqlite(self):
        sentinel = self.directory / "cloud.db"
        with scoped_env(TRADERDASH_ENV=None, DATABASE_URL=None, TRADERDASH_DATABASE=str(sentinel)):
            with patch("account_store.running_on_streamlit_cloud", return_value=True):
                with self.assertRaises(AccountConfigError):
                    accounts.get_user("")
        self.assertFalse(sentinel.exists())

    def test_login_and_reload_keep_the_same_free_account(self):
        signed_in = accounts.authenticate("owner@example.com", PASSWORD)
        loaded = accounts.get_user(self.user.user_id)
        self.assertIsNotNone(signed_in)
        self.assertEqual(signed_in.user_id, loaded.user_id)
        self.assertEqual(loaded.plan, "free")
        self.assertEqual(loaded.subscription_status, "free")
        self.assertIsNone(accounts.authenticate("owner@example.com", "wrong-password-1"))

    def test_account_survives_a_new_process(self):
        database = self.directory / "restart.db"
        script = self.directory / "restart_check.py"
        script.write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            "import accounts\n"
            "action = sys.argv[1]\n"
            "if action == 'create':\n"
            "    user = accounts.create_user('persist@example.com', 'persistent-pass')\n"
            "    if user.plan != 'free' or user.subscription_status != 'free':\n"
            "        raise SystemExit(1)\n"
            "else:\n"
            "    user = accounts.authenticate('persist@example.com', 'persistent-pass')\n"
            "    if user is None or user.plan != 'free' or user.subscription_status != 'free':\n"
            "        raise SystemExit(1)\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env["TRADERDASH_ENV"] = "local"
        env["TRADERDASH_DATABASE"] = str(database)
        env.pop("DATABASE_URL", None)
        for action in ("create", "read"):
            completed = subprocess.run(
                [sys.executable, str(script), action],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_duplicate_email_is_rejected(self):
        with self.assertRaises(AccountError):
            accounts.create_user("owner@example.com", "another-password")

    def test_invalid_plan_and_status_are_rejected(self):
        with self.assertRaises(AccountError):
            accounts.update_user_subscription(
                self.user.user_id,
                plan="premium",
                subscription_status="active",
                stripe_customer_id="cus_test",
                stripe_subscription_id="sub_test",
                subscription_current_period_end=None,
                cancel_at_period_end=False,
            )
        with self.assertRaises(AccountError):
            accounts.update_user_subscription(
                self.user.user_id,
                plan="nordic",
                subscription_status="paid",
                stripe_customer_id="cus_test",
                stripe_subscription_id="sub_test",
                subscription_current_period_end=None,
                cancel_at_period_end=False,
            )
        untouched = accounts.get_user(self.user.user_id)
        self.assertEqual(untouched.plan, "free")

    def test_session_choice_does_not_change_the_stored_plan(self):
        self.assertEqual(accounts.resolve_plan("free", "international"), "free")
        self.assertEqual(accounts.resolve_plan("free", "nordic"), "free")

    def test_password_hash_is_preserved_and_not_plaintext(self):
        connection = sqlite3.connect(self.database)
        try:
            stored = connection.execute(
                "SELECT password_hash FROM users WHERE email = ?",
                ("owner@example.com",),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertTrue(stored.startswith("scrypt$16384$8$1$"))
        self.assertNotIn(PASSWORD, stored)
        self.assertNotIn("password_hash", accounts.User.__dataclass_fields__)

    def test_existing_sqlite_schema_gains_subscription_columns(self):
        legacy = self.directory / "legacy.db"
        connection = sqlite3.connect(legacy)
        connection.execute(
            """
            CREATE TABLE users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                plan TEXT NOT NULL,
                subscription_status TEXT NOT NULL,
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        current_hash = sqlite3.connect(self.database).execute(
            "SELECT password_hash FROM users WHERE email = ?",
            ("owner@example.com",),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO users (
                user_id, email, password_hash, plan, subscription_status,
                stripe_customer_id, stripe_subscription_id, created_at, updated_at
            )
            VALUES ('legacy-user', 'legacy@example.com', ?, 'free', 'free', NULL, NULL, 't', 't')
            """,
            (current_hash,),
        )
        connection.commit()
        connection.close()

        with scoped_env(TRADERDASH_DATABASE=str(legacy)):
            migrated = accounts.authenticate("legacy@example.com", PASSWORD)
            columns = {
                row[1]
                for row in sqlite3.connect(legacy).execute("PRAGMA table_info(users)")
            }
        self.assertIsNotNone(migrated)
        self.assertEqual(migrated.plan, "free")
        self.assertIn("subscription_current_period_end", columns)
        self.assertIn("cancel_at_period_end", columns)

    def test_stripe_event_is_stored_once(self):
        self.assertTrue(accounts.record_stripe_event("evt_once", "checkout.session.completed"))
        self.assertTrue(accounts.stripe_event_already_processed("evt_once"))
        self.assertFalse(accounts.record_stripe_event("evt_once", "checkout.session.completed"))
        connection = sqlite3.connect(self.database)
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM stripe_events WHERE stripe_event_id = ?",
                ("evt_once",),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 1)

    def test_stripe_customer_cannot_be_attached_to_two_accounts(self):
        other = accounts.create_user("other@example.com", "another-password")
        accounts.update_user_subscription(
            self.user.user_id,
            plan="free",
            subscription_status="free",
            stripe_customer_id="cus_shared",
            stripe_subscription_id=None,
            subscription_current_period_end=None,
            cancel_at_period_end=False,
        )
        with self.assertRaises(AccountError):
            accounts.update_user_subscription(
                other.user_id,
                plan="free",
                subscription_status="free",
                stripe_customer_id="cus_shared",
                stripe_subscription_id=None,
                subscription_current_period_end=None,
                cancel_at_period_end=False,
            )

    def test_stripe_user_mapping_uses_the_internal_id_only(self):
        user_id = self.user.user_id
        mapped = account_store.traderdash_user_id_from_stripe_event(
            {"data": {"object": {"client_reference_id": user_id, "customer_email": "other@example.com"}}}
        )
        from_metadata = account_store.traderdash_user_id_from_stripe_event(
            {"data": {"object": {"metadata": {"user_id": user_id, "email": "other@example.com"}}}}
        )
        email_only = account_store.traderdash_user_id_from_stripe_event(
            {"data": {"object": {"customer_email": "owner@example.com", "metadata": {"email": "owner@example.com"}}}}
        )
        self.assertEqual(mapped, user_id)
        self.assertEqual(from_metadata, user_id)
        self.assertIsNone(email_only)

    def test_streamlit_pages_do_not_receive_database_secrets(self):
        for name in ("app.py", "account_page.py", "plans.py", "access.py", "universes.py"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("SUPABASE_SERVICE_ROLE", text)
            self.assertNotIn("service_role", text)
            self.assertNotIn("update_user_subscription", text)
            self.assertNotIn("DATABASE_URL", text)

    def test_checkout_and_paid_plans_are_not_activated(self):
        import plans

        self.assertEqual(plans.request_checkout("nordic"), plans.CHECKOUT_UNAVAILABLE)
        function = (ROOT / "supabase" / "functions" / "stripe-webhook" / "index.ts").read_text(encoding="utf-8")
        config = (ROOT / "supabase" / "config.toml").read_text(encoding="utf-8")
        migration = (ROOT / "supabase" / "migrations" / "20261030160000_accounts.sql").read_text(encoding="utf-8")
        self.assertIn("const ENTITLEMENT_UPDATES_ENABLED = false", function)
        self.assertNotIn("plan =", function)
        self.assertIn("verify_jwt = false", config)
        self.assertIn("create table if not exists public.users", migration)
        self.assertIn("create table if not exists public.stripe_events", migration)
        self.assertNotIn("create table if not exists public.subscriptions", migration)


if __name__ == "__main__":
    unittest.main()
