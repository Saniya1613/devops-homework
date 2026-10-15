"""Test setup: every test runs against a throw-away SQLite database, never the real PostgreSQL."""
import os

os.environ["DATABASE_URL"] = "sqlite:///./test_careslot.db"

from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_db_file():
    yield
    engine.dispose()
    if os.path.exists("test_careslot.db"):
        os.remove("test_careslot.db")


@pytest.fixture()
def doctor(client):
    r = client.post("/api/doctors", json={"name": "Dr. Test Sharma", "specialty": "General Physician", "room": "9"})
    assert r.status_code == 201
    return r.json()


def slot(hours_from_now: int = 24, minute: int = 0) -> str:
    """ISO timestamp for a future slot, rounded to the hour."""
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return (base + timedelta(hours=hours_from_now, minutes=minute)).isoformat()


@pytest.fixture()
def booking(doctor):
    def _make(**overrides):
        payload = {"doctor_id": doctor["id"], "patient_name": "Riya Patil", "patient_phone": "+91 98765 43210",
                   "reason": "Fever", "scheduled_at": slot()}
        payload.update(overrides)
        return payload
    return _make
