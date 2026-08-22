from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_dashboard_contract():
    response = client.get("/dashboard")

    assert response.status_code == 200, response.text

    data = response.json()

    assert isinstance(data, dict)
    assert isinstance(data.get("tasks", []), list)
    assert isinstance(data.get("meetings", []), list)
    assert isinstance(data.get("availability", []), list)
    assert isinstance(data.get("reminders", []), list)


def test_planner_contract():
    response = client.get("/planner/")

    assert response.status_code == 200, response.text

    data = response.json()

    assert isinstance(data, dict)
    assert "planning_date" in data
    assert isinstance(data.get("prioritized_tasks", []), list)
    assert isinstance(data.get("schedule", []), list)
    assert isinstance(data.get("unscheduled_tasks", []), list)


def test_ai_endpoint_rejects_empty_message():
    response = client.post("/ai/process", json={"message": ""})

    assert response.status_code in (400, 422), response.text