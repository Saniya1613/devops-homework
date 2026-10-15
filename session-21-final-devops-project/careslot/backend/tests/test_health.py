def test_health(client):
    assert client.get("/health").json() == {"status": "UP"}


def test_ready_checks_database(client):
    r = client.get("/ready")
    assert r.status_code == 200 and r.json() == {"status": "READY"}


def test_root_identifies_service(client):
    body = client.get("/").json()
    assert body["service"] == "CareSlot API" and body["docs"] == "/docs"


def test_metrics_endpoint_is_prometheus_format(client):
    client.get("/api/doctors")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text
    assert "careslot_appointments_booked_total" in r.text
