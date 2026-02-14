import os
from pathlib import Path

import pytest

# Required runtime env vars.
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("LLM_MODEL", "gpt-5.2")
os.environ.setdefault("DASHBOARD_PORT", "3000")
os.environ.setdefault("NOTIFICATION_TEXT_PHONE", "")
os.environ.setdefault("ARTIFACTS_DIR", "/tmp/agents-artifacts")

TEST_DB = Path(__file__).resolve().parent / "test.sqlite3"
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{TEST_DB}")

from app.db import engine  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
