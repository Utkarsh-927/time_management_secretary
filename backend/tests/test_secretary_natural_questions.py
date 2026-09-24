import requests
import pytest


BASE_URL = "http://127.0.0.1:8000"

TEST_USER_ID = "secretary_test_user"

TEST_NOTE = (
    "I gave Arun the ABC website project. "
    "He needs to finish the homepage and contact form by Friday. "
    "The budget is 25000 INR. "
    "I want to review it after 3 days."
)


def api_process(message: str):
    response = requests.post(
        f"{BASE_URL}/ai/process",
        json={
            "message": message,
            "user_id": TEST_USER_ID,
        },
        timeout=120,
    )

    assert response.status_code == 200, (
        f"HTTP {response.status_code}: {response.text}"
    )

    return response.json()


@pytest.fixture(scope="session", autouse=True)
def seed_secretary_test_data():
    """
    Seed one isolated secretary dataset for the entire test session.
    """

    # First create the known secretary note.
    response = requests.post(
        f"{BASE_URL}/ai/process",
        json={
            "message": TEST_NOTE,
            "user_id": TEST_USER_ID,
        },
        timeout=120,
    )

    assert response.status_code == 200, (
        f"Failed to seed test data.\n"
        f"HTTP {response.status_code}: {response.text}"
    )

    yield


SECRETARY_QUESTIONS = [
    (
        "What project did I give Arun?",
        ["Arun", "ABC website project"],
    ),
    (
        "What did I assign Arun?",
        ["Arun", "ABC website project"],
    ),
    (
        "What is Arun responsible for?",
        ["Arun", "ABC website project"],
    ),
    (
        "What task did Arun get?",
        ["Arun", "homepage", "contact form"],
    ),
    (
        "What does Arun need to finish?",
        ["Arun", "homepage", "contact form"],
    ),
    (
        "What was the budget for the ABC website project?",
        ["25000", "INR"],
    ),
    (
        "When is the ABC website project due?",
        ["ABC website project"],
    ),
    (
        "What do I need to review?",
        ["ABC website project"],
    ),
    (
        "What should I follow up on?",
        ["ABC website project"],
    ),
]


@pytest.mark.parametrize(
    "question,expected_keywords",
    SECRETARY_QUESTIONS,
)
def test_secretary_question(question, expected_keywords):
    data = api_process(question)

    answer = data.get("message", "")

    print()
    print("=" * 70)
    print(f"QUESTION : {question}")
    print(f"ANSWER   : {answer}")
    print("=" * 70)

    assert answer, "API returned an empty message."

    answer_lower = answer.lower()

    missing = [
        keyword
        for keyword in expected_keywords
        if keyword.lower() not in answer_lower
    ]

    assert not missing, (
        f"\nQuestion: {question}"
        f"\nAnswer: {answer}"
        f"\nMissing expected information: {missing}"
    )

    # Catch obvious broken Gemma output.
    garbage_markers = [
        "```",
        "2_",
        "8_",
        "if,0",
        "the\n2.",
    ]

    broken_output = any(
        marker.lower() in answer_lower
        for marker in garbage_markers
    )

    assert not broken_output, (
        f"\nSecretary returned malformed output."
        f"\nQuestion: {question}"
        f"\nAnswer: {answer}"
    )