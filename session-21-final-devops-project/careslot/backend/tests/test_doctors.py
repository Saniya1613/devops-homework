def test_create_and_list_doctors(client, doctor):
    assert doctor["name"] == "Dr. Test Sharma" and doctor["active"] is True
    names = [d["name"] for d in client.get("/api/doctors").json()]
    assert "Dr. Test Sharma" in names


def test_get_update_delete_doctor(client, doctor):
    url = f"/api/doctors/{doctor['id']}"
    assert client.get(url).json()["specialty"] == "General Physician"
    r = client.put(url, json={"room": "12", "active": False})
    assert r.status_code == 200 and r.json()["room"] == "12" and r.json()["active"] is False
    assert client.get("/api/doctors", params={"active_only": True}).json() == []
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404


def test_doctor_validation(client):
    assert client.post("/api/doctors", json={"name": "X", "specialty": "ENT"}).status_code == 422
