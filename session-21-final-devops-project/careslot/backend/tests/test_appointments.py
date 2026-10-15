from conftest import slot


def test_book_and_get_appointment(client, booking):
    r = client.post("/api/appointments", json=booking())
    assert r.status_code == 201
    appt = r.json()
    assert appt["status"] == "SCHEDULED" and appt["doctor_name"] == "Dr. Test Sharma"
    fetched = client.get(f"/api/appointments/{appt['id']}").json()
    assert fetched["patient_name"] == "Riya Patil" and fetched["reason"] == "Fever"


def test_double_booking_is_rejected(client, booking):
    assert client.post("/api/appointments", json=booking(scheduled_at=slot(30))).status_code == 201
    overlap = client.post("/api/appointments", json=booking(patient_name="Aman Gupta", scheduled_at=slot(30, 10)))
    assert overlap.status_code == 409 and "already booked" in overlap.json()["detail"]
    # right after the first 20-minute slot is free
    assert client.post("/api/appointments", json=booking(patient_name="Aman Gupta",
                                                         scheduled_at=slot(30, 20))).status_code == 201


def test_cancelled_slot_can_be_rebooked(client, booking):
    first = client.post("/api/appointments", json=booking(scheduled_at=slot(40))).json()
    client.put(f"/api/appointments/{first['id']}", json={"status": "CANCELLED"})
    assert client.post("/api/appointments", json=booking(patient_name="Neha Rao",
                                                         scheduled_at=slot(40))).status_code == 201


def test_reschedule_and_status_flow(client, booking):
    appt = client.post("/api/appointments", json=booking(scheduled_at=slot(50))).json()
    url = f"/api/appointments/{appt['id']}"
    r = client.put(url, json={"scheduled_at": slot(51)})
    assert r.status_code == 200 and r.json()["scheduled_at"].startswith(slot(51)[:16])
    for state in ("CHECKED_IN", "COMPLETED"):
        assert client.put(url, json={"status": state}).json()["status"] == state


def test_filters_and_stats(client, booking):
    a = client.post("/api/appointments", json=booking(scheduled_at=slot(60))).json()
    client.post("/api/appointments", json=booking(patient_name="Kabir Shah", scheduled_at=slot(61)))
    client.put(f"/api/appointments/{a['id']}", json={"status": "COMPLETED"})
    assert len(client.get("/api/appointments", params={"status": "completed"}).json()) == 1
    stats = client.get("/api/appointments/stats").json()
    assert stats["total"] == 2 and stats["completed"] == 1 and stats["scheduled"] == 1
    assert stats["byDoctor"][0]["appointments"] == 2


def test_delete_appointment(client, booking):
    appt = client.post("/api/appointments", json=booking()).json()
    assert client.delete(f"/api/appointments/{appt['id']}").status_code == 204
    assert client.get(f"/api/appointments/{appt['id']}").status_code == 404


def test_booking_validation_and_unknown_doctor(client, booking):
    assert client.post("/api/appointments", json=booking(patient_phone="call me")).status_code == 422
    assert client.post("/api/appointments", json=booking(duration_minutes=500)).status_code == 422
    assert client.post("/api/appointments", json=booking(doctor_id=999)).status_code == 404


def test_inactive_doctor_cannot_be_booked(client, doctor, booking):
    client.put(f"/api/doctors/{doctor['id']}", json={"active": False})
    assert client.post("/api/appointments", json=booking()).status_code == 409
