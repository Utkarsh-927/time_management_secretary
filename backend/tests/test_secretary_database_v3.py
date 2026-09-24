from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.database.database import Base
from backend.app.models import RawNote, ConversationSession, ConversationMessage, Entity, Fact, EntityRelationship, Event, Memory, Embedding, Task
from backend.app.services.secretary_memory import store_user_note


def test_v3_schema_creates_and_stores_raw_note(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'v3.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    note, conversation = store_user_note(db, "I gave Arun the ABC website project.")
    assert note.raw_text == "I gave Arun the ABC website project."
    assert note.processed is False
    assert conversation.id is not None
    assert db.query(ConversationMessage).filter_by(conversation_id=conversation.id, role="user").count() == 1
    expected = {"raw_notes", "entities", "facts", "entity_relationships", "events", "memories", "embeddings", "conversation_sessions", "conversation_messages", "tasks", "meetings", "reminders", "availability"}
    from sqlalchemy import inspect
    assert expected.issubset(set(inspect(engine).get_table_names()))
    db.close()
