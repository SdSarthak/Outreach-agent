"""Shared fixtures.

Every test runs against a temporary SQLite file with ``DRY_RUN`` forced on, so
no test can reach the network, dial a phone number or send an email.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_settings, reset_settings  # noqa: E402
from src.database import Customer, DatabaseManager  # noqa: E402

# Environment that must not leak in from the developer's shell or .env file.
MANAGED_ENV = (
    "DRY_RUN",
    "DATABASE_URL",
    "DB_ECHO",
    "LOG_LEVEL",
    "LOG_FILE",
    "OPENAI_API_KEY",
    "OPENAI_TIMEOUT",
    "HTTP_TIMEOUT",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_AGENT_ID",
    "ELEVENLABS_PHONE_NUMBER_ID",
    "ELEVENLABS_BASE_URL",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "GMAIL_ADDRESS",
    "GMAIL_TOKEN_PATH",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "CALL_POLL_INTERVAL",
    "CALL_MAX_WAIT",
    "RETRY_ATTEMPTS",
    "RETRY_BACKOFF",
)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    """Give every test a clean, dry-run configuration."""
    monkeypatch.setattr("src.config.load_dotenv", lambda *args, **kwargs: False)
    for name in MANAGED_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DRY_RUN", "true")
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def settings(isolated_settings):
    return get_settings(refresh=True)


@pytest.fixture
def db(tmp_path):
    manager = DatabaseManager(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    manager.init_db()
    try:
        yield manager
    finally:
        manager.close()


@pytest.fixture
def customer_factory(db):
    """Insert customers and return their ids."""

    def _create(**overrides):
        fields = {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "+15550100",
            "company": "Analytical Engines",
            "industry": "Technology",
            "engagement_score": 0.8,
        }
        fields.update(overrides)
        with db.session_scope() as session:
            customer = Customer(**fields)
            session.add(customer)
            session.flush()
            return customer.id

    return _create
