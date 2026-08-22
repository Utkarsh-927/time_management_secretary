from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)

MESSAGE = (
    "I need an E2E AI Python assignment tomorrow. "
    "It will take one hour and it is important."
)


def _json(response):
    assert response.headers.get("content-type", "").startswith(
        "application/json"
    ), response.text
    return response.json()


def test_real_ai_to_database_workflow():
    """
    Real AI integration test.

    This intentionally calls /ai/process, so the local Gemma parser is
    exercised. We then verify the created task through /dashboard.

    Expected interpretation:
      - task is created
      - duration is 60 minutes
      - importance is 4 ("important")
      - deadline is populated

    The task is removed in finally so repeated test runs do not accumulate
    test data.
    """

    created_task = None

    try:
        ai_response = client.post(
            "/ai/process",
            json={"message": MESSAGE},
        )

        assert ai_response.status_code in (200, 201), (
            f"/ai/process failed: "
            f"{ai_response.status_code} {ai_response.text}"
        )

        ai_data = _json(ai_response)

        # The endpoint should return a JSON object describing the operation.
        assert isinstance(ai_data, dict)

        dashboard_response = client.get("/dashboard")
        assert dashboard_response.status_code == 200, (
            dashboard_response.text
        )

        dashboard = _json(dashboard_response)

        tasks = dashboard.get("tasks", [])
        assert isinstance(tasks, list)

        matching = [
            task
            for task in tasks
            if "E2E AI Python assignment" in str(
                task.get("title", "")
            )
        ]

        assert matching, (
            "AI request succeeded, but the created task was not "
            "found in /dashboard."
        )

        created_task = matching[-1]

        assert created_task.get("estimated_duration") == 60
        assert created_task.get("importance") == 4
        assert created_task.get("deadline") is not None

    finally:
        if created_task and created_task.get("id") is not None:
            delete_response = client.delete(
                f"/tasks/{created_task['id']}"
            )

            assert delete_response.status_code in (200, 204), (
                f"Cleanup failed: {delete_response.status_code} "
                f"{delete_response.text}"
            )