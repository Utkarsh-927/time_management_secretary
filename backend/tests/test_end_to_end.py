from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def _json(response):
    assert response.headers.get("content-type", "").startswith(
        "application/json"
    ), response.text
    return response.json()


def _create(path, payload):
    response = client.post(path, json=payload)
    assert response.status_code in (200, 201), (
        f"POST {path} failed: {response.status_code} {response.text}"
    )
    return _json(response)


def _delete(path):
    response = client.delete(path)
    assert response.status_code in (200, 204), (
        f"DELETE {path} failed: {response.status_code} {response.text}"
    )


def test_real_management_workflow():
    """
    End-to-end smoke test:

        create records
        -> dashboard sees them
        -> planner sees the task
        -> update the task
        -> complete the task
        -> cleanup

    This does NOT launch Gemma. The parser/command tests already cover
    natural-language extraction and command interpretation; this test
    validates the real application/database/API chain around them.
    """

    suffix = datetime.now().strftime("%Y%m%d%H%M%S%f")
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)

    task = None
    meeting = None
    availability = None

    try:
        task = _create(
            "/tasks/",
            {
                "title": f"E2E Python assignment {suffix}",
                "description": "End-to-end integration test",
                "deadline": (
                    datetime.combine(
                        tomorrow,
                        datetime.min.time(),
                    )
                    + timedelta(hours=18)
                ).isoformat(),
                "estimated_duration": 60,
                "importance": 5,
            },
        )

        meeting_start = datetime.combine(
            tomorrow,
            datetime.min.time(),
        ) + timedelta(hours=15)

        meeting = _create(
            "/meetings/",
            {
                "title": f"E2E Team Meeting {suffix}",
                "description": "End-to-end integration test",
                "start_time": meeting_start.isoformat(),
                "end_time": (
                    meeting_start + timedelta(hours=1)
                ).isoformat(),
                "location": "Online",
                "participants": "Integration Test",
            },
        )

        availability = _create(
            "/availability/",
            {
                "start_date": today.isoformat(),
                "end_date": tomorrow.isoformat(),
                "start_time": "09:00",
                "end_time": "18:00",
                "recurrence": "none",
                "weekdays": "",
            },
        )

        task_id = task["id"]
        meeting_id = meeting["id"]
        availability_id = availability["id"]

        dashboard_response = client.get("/dashboard")
        assert dashboard_response.status_code == 200, dashboard_response.text
        dashboard = _json(dashboard_response)

        assert any(
            item["id"] == task_id
            for item in dashboard.get("tasks", [])
        )
        meeting_response = client.get("/meetings/")
        assert meeting_response.status_code == 200, meeting_response.text

        meetings = _json(meeting_response)

        assert any(
            item["id"] == meeting_id
            for item in meetings
        )
        assert any(
            item["id"] == availability_id
            for item in dashboard.get("availability", [])
        )

        planner_response = client.get("/planner/")
        assert planner_response.status_code == 200, planner_response.text
        planner = _json(planner_response)

        assert "planning_date" in planner
        assert isinstance(planner.get("prioritized_tasks", []), list)
        assert isinstance(planner.get("schedule", []), list)
        assert isinstance(planner.get("unscheduled_tasks", []), list)

        planner_task_ids = {
            item.get("task_id")
            for item in planner.get("prioritized_tasks", [])
        }
        scheduled_task_ids = {
            item.get("task_id")
            for item in planner.get("schedule", [])
        }
        unscheduled_task_ids = {
            item.get("task_id")
            for item in planner.get("unscheduled_tasks", [])
        }

        assert task_id in (
            planner_task_ids
            | scheduled_task_ids
            | unscheduled_task_ids
        )

        update_response = client.put(
            f"/tasks/{task_id}",
            json={"importance": 3},
        )
        assert update_response.status_code == 200, update_response.text

        updated_task = _json(update_response)
        assert updated_task["importance"] == 3

        complete_response = client.patch(
            f"/tasks/{task_id}/complete"
        )
        assert complete_response.status_code == 200, (
            complete_response.text
        )

        dashboard_after = _json(client.get("/dashboard"))
        saved_task = next(
            (
                item
                for item in dashboard_after.get("tasks", [])
                if item["id"] == task_id
            ),
            None,
        )

        # Depending on the dashboard implementation, completed tasks may
        # remain visible or may be filtered out. Either result is valid.
        if saved_task is not None:
            assert saved_task.get("status") == "completed"

    finally:
        if meeting and meeting.get("id") is not None:
            _delete(f"/meetings/{meeting['id']}")

        if task and task.get("id") is not None:
            _delete(f"/tasks/{task['id']}")

        if availability and availability.get("id") is not None:
            _delete(f"/availability/{availability['id']}")