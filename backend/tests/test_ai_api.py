from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_ai_endpoint_rejects_empty_message():
    response = client.post(
        "/ai/process",
        json={
            "message": ""
        }
    )

    assert response.status_code == 400


def test_ai_endpoint_rejects_whitespace_message():
    response = client.post(
        "/ai/process",
        json={
            "message": "   "
        }
    )

    assert response.status_code == 400