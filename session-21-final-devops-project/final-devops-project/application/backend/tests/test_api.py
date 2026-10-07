import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    if os.path.exists("test.db"):
        os.remove("test.db")
    with TestClient(app) as c:      # context manager runs the startup event (creates tables)
        yield c
    os.remove("test.db")


def test_health(client):
    assert client.get("/health").json() == {"status": "UP"}


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200 and r.json()["status"] == "READY"


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "TaskBoard API"


def test_create_and_get_task(client):
    r = client.post("/api/tasks", json={"title": "Deploy application", "priority": "HIGH", "assignee": "Saniya"})
    assert r.status_code == 201
    task = r.json()
    assert task["title"] == "Deploy application" and task["status"] == "TODO"
    assert client.get(f"/api/tasks/{task['id']}").json()["assignee"] == "Saniya"


def test_update_and_stats(client):
    tid = client.post("/api/tasks", json={"title": "Write README"}).json()["id"]
    r = client.put(f"/api/tasks/{tid}", json={"status": "DONE"})
    assert r.status_code == 200 and r.json()["status"] == "DONE"
    stats = client.get("/api/tasks/stats").json()
    assert stats["total"] >= 2 and stats["done"] >= 1


def test_validation_error(client):
    assert client.post("/api/tasks", json={"title": ""}).status_code == 422
    assert client.post("/api/tasks", json={"title": "x", "priority": "URGENT"}).status_code == 422


def test_delete_and_404(client):
    tid = client.post("/api/tasks", json={"title": "temp"}).json()["id"]
    assert client.delete(f"/api/tasks/{tid}").status_code == 204
    assert client.get(f"/api/tasks/{tid}").status_code == 404


def test_metrics_endpoint(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text
