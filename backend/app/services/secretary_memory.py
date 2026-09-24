from datetime import datetime
from sqlalchemy.orm import Session
from ..models import ConversationMessage, ConversationSession, RawNote

DEFAULT_USER_ID = "default"


def get_or_create_conversation(db: Session, user_id: str = DEFAULT_USER_ID, conversation_id: int | None = None):
    if conversation_id is not None:
        session = db.query(ConversationSession).filter(
            ConversationSession.id == conversation_id,
            ConversationSession.user_id == user_id,
        ).first()
        if session:
            session.last_activity_at = datetime.utcnow()
            return session

    session = ConversationSession(user_id=user_id, status="active")
    db.add(session)
    db.flush()
    return session


def store_user_note(
    db: Session,
    raw_text: str,
    user_id: str = DEFAULT_USER_ID,
    conversation_id: int | None = None,
    source: str = "chat",
):
    """Persist the exact user text before any AI extraction or command handling."""
    conversation = get_or_create_conversation(db, user_id, conversation_id)
    message = ConversationMessage(
        conversation_id=conversation.id,
        role="user",
        content=raw_text,
    )
    note = RawNote(
        user_id=user_id,
        raw_text=raw_text,
        source=source,
        conversation_id=conversation.id,
        processed=False,
        processing_status="pending",
    )
    conversation.last_activity_at = datetime.utcnow()
    db.add_all([message, note])
    db.commit()
    db.refresh(note)
    return note, conversation


def store_assistant_message(db: Session, conversation_id: int, content: str):
    message = ConversationMessage(
        conversation_id=conversation_id,
        role="assistant",
        content=content,
    )
    conversation = db.query(ConversationSession).filter(ConversationSession.id == conversation_id).first()
    if conversation:
        conversation.last_activity_at = datetime.utcnow()
    db.add(message)
    db.commit()
    return message
