from app.services.source_extractor import (
    extract_source_information,
    merge_source_first,
)


MESSAGE = (
    "I gave Arun the ABC website project. "
    "He needs to finish the homepage and contact form by Friday. "
    "The budget is 25000 INR. "
    "I want to review it after 3 days."
)


def test_source_extractor_captures_critical_secretary_information():
    data = extract_source_information(MESSAGE)

    entity_names = {
        item["name"]
        for item in data["entities"]
    }

    assert "Arun" in entity_names
    assert "ABC website project" in entity_names

    facts = data["facts"]

    assert any(
        item["entity"] == "ABC website project"
        and item["key"] == "budget"
        and item["value"] == 25000
        and item["unit"] == "INR"
        for item in facts
    )

    relationships = data["relationships"]

    assert any(
        item["source"] == "Arun"
        and item["relationship_type"] == "responsible_for"
        and item["target"] == "ABC website project"
        for item in relationships
    )

    events = data["events"]

    assert any(
        item["type"] == "DEADLINE"
        and "Friday" in item["title"]
        for item in events
    )

    assert any(
        item["type"] == "REVIEW"
        and "after 3 days" in item["title"]
        for item in events
    )


def test_hallucinated_model_entity_is_rejected():
    source = extract_source_information(MESSAGE)

    bad_model = {
        "entities": [
            {
                "type": "PERSON",
                "name": "Arund",
                "description": None,
            }
        ],
        "facts": [],
        "relationships": [],
        "events": [],
        "memories": [],
    }

    merged = merge_source_first(
        source,
        bad_model,
        MESSAGE,
    )

    entity_names = {
        item["name"]
        for item in merged["entities"]
    }

    assert "Arun" in entity_names
    assert "Arund" not in entity_names


def test_hallucinated_number_is_rejected():
    source = extract_source_information(MESSAGE)

    bad_model = {
        "entities": [
            {
                "type": "PROJECT",
                "name": "ABC website project",
            }
        ],
        "facts": [
            {
                "entity": "ABC website project",
                "key": "budget",
                "value": 99999,
                "value_type": "number",
                "unit": "INR",
                "confidence": 1.0,
            }
        ],
        "relationships": [],
        "events": [],
        "memories": [],
    }

    merged = merge_source_first(
        source,
        bad_model,
        MESSAGE,
    )

    budgets = [
        item
        for item in merged["facts"]
        if item["key"] == "budget"
    ]

    assert any(item["value"] == 25000 for item in budgets)
    assert not any(item["value"] == 99999 for item in budgets)