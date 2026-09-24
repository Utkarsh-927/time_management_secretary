from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.models import RawNote, ConversationSession
from app.services import secretary_processor


MESSAGE = (
    "I gave Arun the ABC website project. He needs to finish the homepage and "
    "contact form by Friday. The budget is 25000 INR. I want to review it after 3 days."
)


def secretary_payload():
    return {
        "entities": [
            {"type": "PERSON", "name": "Arun", "description": None},
            {"type": "PROJECT", "name": "ABC website project", "description": None},
        ],
        "facts": [{"entity": "ABC website project", "key": "budget", "value": 25000,
                   "value_type": "number", "unit": "INR", "confidence": 1.0}],
        "relationships": [{"source": "Arun", "relationship_type": "responsible_for",
                            "target": "ABC website project", "confidence": 1.0}],
        "events": [
            {"type": "ASSIGNMENT", "title": "ABC website project assigned to Arun",
             "primary_entity": "ABC website project"},
            {"type": "DEADLINE", "title": "ABC website project work due Friday",
             "event_time": "Friday", "primary_entity": "ABC website project"},
            {"type": "REVIEW", "title": "Review ABC website project",
             "description": "Review the project 3 days after the assignment.",
             "event_time": "after 3 days", "primary_entity": "ABC website project"},
        ],
        "memories": [{"memory_type": "PROJECT_CONTEXT", "importance": 0.8,
                      "confidence": 0.9, "entity": "ABC website project",
                      "content": "Arun is responsible for the ABC website project."}],
    }


def pass_response(payload):
    def run(prompt, max_tokens=None):
        kind = __import__("re").search(r"Extract only (entities|facts|relationships|events|memories)", prompt).group(1)
        return __import__("json").dumps({kind: payload[kind]})
    return run


def test_process_raw_note(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    conversation = ConversationSession(user_id="default", status="active")
    db.add(conversation)
    db.flush()

    note = RawNote(
        user_id="default",
        raw_text="I gave Arun the ABC website project.",
        source="chat",
        conversation_id=conversation.id,
        processed=False,
        processing_status="pending",
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    monkeypatch.setattr(
        secretary_processor,
        "extract_secretary_information",
        lambda message: {
            "entities": [
                {"type": "PERSON", "name": "Arun"},
                {"type": "PROJECT", "name": "ABC website project"},
                {"type": "TASK", "name": "Finish homepage"},
            ],
            "facts": [
                {
                    "entity": "ABC website project",
                    "key": "budget",
                    "value": 25000,
                    "value_type": "number",
                    "unit": "INR",
                    "confidence": 1.0,
                }
            ],
            "relationships": [
                {
                    "source": "Arun",
                    "relationship_type": "assigned_to",
                    "target": "ABC website project",
                    "confidence": 1.0,
                }
            ],
            "events": [
                {
                    "type": "ASSIGNMENT",
                    "title": "ABC website project assigned to Arun",
                    "primary_entity": "ABC website project",
                    "confidence": 1.0,
                }
            ],
            "memories": [
                {
                    "type": "project",
                    "content": "Arun is responsible for the ABC website project.",
                    "importance": 0.9,
                    "confidence": 1.0,
                    "entity": "ABC website project",
                }
            ],
        },
    )

    result = secretary_processor.process_raw_note(db, note)

    assert result["status"] == "completed"
    assert result["entities"] == 3
    assert result["facts"] == 1
    assert result["relationships"] == 1
    assert result["events"] == 1
    assert result["memories"] == 1
    assert db.query(RawNote).get(note.id).processed is True


def test_secretary_parser_accepts_fences_and_repairs_missing_comma(monkeypatch):
    payload = secretary_payload()
    malformed = __import__("json").dumps(payload).replace(
        '], "memories"', '] "memories"'
    )
    monkeypatch.setattr(secretary_processor, "_run_gemma", pass_response(payload))

    result = secretary_processor.extract_secretary_information(MESSAGE)

    assert result["facts"][0]["value"] == 25000
    assert isinstance(result["entities"], list)
    assert {event["type"] for event in result["events"]} == {"ASSIGNMENT", "DEADLINE", "REVIEW"}
    assert all(event["type"] != "MEETING" for event in result["events"])
    assert "estimated_duration" not in str(result)


def test_secretary_parser_accepts_valid_json_and_trailing_comma():
    valid = __import__("json").dumps(secretary_payload())
    assert secretary_processor.parse_secretary_response(valid)["relationships"][0]["relationship_type"] == "responsible_for"

    trailing_comma = valid[:-1] + ",}"
    result = secretary_processor.parse_secretary_response(trailing_comma)
    assert result["facts"][0]["value"] == 25000
    assert result["facts"][0]["unit"] == "INR"


def test_secretary_parser_uses_model_json_after_echoed_prompt():
    echoed_schema = '{"entities":[],"facts":[],"relationships":[],"events":[],"memories":[]}'
    raw = f"prompt text {echoed_schema}\nmodel answer\n{__import__('json').dumps(secretary_payload())}"
    assert secretary_processor.parse_secretary_response(raw)["entities"][0]["name"] == "Arun"


def test_secretary_parser_rejects_invalid_and_empty_responses_with_raw_diagnostic():
    for response in ("not json", '{"entities":[],"facts":[],"relationships":[],"events":[],"memories":[]}'):
        try:
            secretary_processor.parse_secretary_response(response)
        except secretary_processor.SecretaryExtractionError as error:
            assert "Raw response (truncated)" in str(error)
        else:
            raise AssertionError("Invalid or empty extraction must be rejected")


def test_small_model_misplaced_amount_deadline_and_review_are_normalized():
    raw = {
        "entities": [
            {"type": "PERSON", "name": "Arun"},
            {"type": "PROJECT", "name": "ABC website project"},
            {"type": "AMOUNT", "value": 25000, "currency": "INR"},
            {"type": "DEADLINE", "name": "Friday"},
            {"type": "REVIEW", "title": "review after 3 days"},
        ], "facts": [], "relationships": [], "events": [], "memories": [],
    }
    result = secretary_processor._normalize_secretary_semantics(raw, MESSAGE)
    assert result["facts"] == [{"entity": "ABC website project", "key": "budget",
                                 "value": 25000, "value_type": "number", "unit": "INR"}]
    assert result["relationships"][0]["relationship_type"] == "responsible_for"
    assert {event["type"] for event in result["events"]} == {"DEADLINE", "REVIEW"}
    assert all(event["type"] != "MEETING" for event in result["events"])


def test_one_bad_pass_does_not_discard_successful_passes(monkeypatch):
    payload = secretary_payload()

    def run(prompt, max_tokens=None):
        kind = __import__("re").search(
            r"Extract only (entities|facts|relationships|events|memories)",
            prompt,
        ).group(1)

        return (
            "not json"
            if kind == "memories"
            else __import__("json").dumps(
                {kind: payload[kind]}
            )
        )

    monkeypatch.setattr(
        secretary_processor,
        "_run_gemma",
        run,
    )

    result = secretary_processor.extract_secretary_information(MESSAGE)

    assert result["entities"]
    assert result["facts"]
    assert result["memories"]


def test_all_bad_passes_fail_safely(monkeypatch):
    monkeypatch.setattr(
        secretary_processor,
        "_run_gemma",
        lambda prompt, max_tokens=None: "not json",
    )

    monkeypatch.setattr(
        secretary_processor,
        "extract_source_information",
        lambda message: secretary_processor._empty_extraction(),
    )

    try:
        secretary_processor.extract_secretary_information(MESSAGE)

    except secretary_processor.SecretaryExtractionError as error:
        assert (
            "Secretary extraction produced no grounded information"
            in str(error)
        )

    else:
        raise AssertionError(
            "All unusable extraction sources must fail"
        )


def test_grounding_rejects_mutated_names_and_ungrounded_numbers():
    source = "I gave Arun the ABC website project. The budget is 25000 INR."
    data = {
        "entities": [{"type": "PERSON", "name": "Arund"}, {"type": "PROJECT", "name": "ABC website project"}],
        "facts": [{"entity": "ABC website project", "key": "budget", "value": 250000, "value_type": "number", "unit": "INR"}],
        "relationships": [{"source": "Arund", "relationship_type": "responsible_for", "target": "ABC website project"}],
        "events": [], "memories": [{"content": "Arund owns the project.", "entity": "Arund"}],
    }
    result = secretary_processor._ground_secretary_data(data, source)
    assert [item["name"] for item in result["entities"]] == ["ABC website project"]
    assert result["facts"] == []
    assert result["relationships"] == []
    assert result["memories"] == []


def test_grounding_accepts_exact_numeric_fact_and_canonical_relationship():
    source = "I gave Arun the ABC website project. The budget is 25000 INR."
    data = secretary_payload()
    result = secretary_processor._ground_secretary_data(data, source)
    assert result["facts"][0]["value"] == 25000
    assert result["facts"][0]["unit"] == "INR"
    assert result["relationships"][0]["source"] == "Arun"


def test_invalid_secretary_extraction_marks_note_failed(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    conversation = ConversationSession(user_id="default", status="active")
    db.add(conversation)
    db.flush()
    note = RawNote(user_id="default", raw_text=MESSAGE, source="chat", conversation_id=conversation.id)
    db.add(note)
    db.commit()

    monkeypatch.setattr(secretary_processor, "extract_secretary_information", lambda message: secretary_processor.parse_secretary_response("not json"))

    try:
        secretary_processor.process_raw_note(db, note)
    except secretary_processor.SecretaryExtractionError:
        pass
    else:
        raise AssertionError("Invalid extraction must fail processing")

    failed = db.query(RawNote).filter_by(id=note.id).one()
    assert failed.processed is False
    assert failed.processing_status == "failed"
    assert "JSON object" in failed.processing_error


def test_exact_message_creates_secretary_knowledge(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    conversation = ConversationSession(user_id="default", status="active")
    db.add(conversation)
    db.flush()
    note = RawNote(user_id="default", raw_text=MESSAGE, source="chat", conversation_id=conversation.id)
    db.add(note)
    db.commit()
    monkeypatch.setattr(secretary_processor, "_run_gemma", pass_response(secretary_payload()))

    result = secretary_processor.process_raw_note(db, note)

    from app.models import Entity, Fact, EntityRelationship, Event, Memory
    assert result["status"] == "completed"
    assert {entity.name for entity in db.query(Entity).all()} >= {"Arun", "ABC website project"}
    assert db.query(Fact).filter_by(key="budget").one().value_number == 25000
    assert db.query(EntityRelationship).filter_by(relationship_type="responsible_for").count() == 1
    assert {event.event_type for event in db.query(Event).all()} == {"ASSIGNMENT", "DEADLINE", "REVIEW"}
    assert db.query(Memory).filter_by(memory_type="PROJECT_CONTEXT").count() == 1
