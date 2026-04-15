import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select
from sqlalchemy import func

from models import ChatSession, ChatMessage
from schemas import PaginatedChatSessionResponse, ChatSessionResponse, ChatSessionDetailResponse, ChatMessageResponse


CHAT_SESSION_PAGE_SIZE = 20


def create_chat_session(owner_id: uuid.UUID, owner_role: str, session: Session) -> ChatSession:
    chat_session = ChatSession(
        owner_id=owner_id,
        owner_role=owner_role,
        title="New Chat",
    )
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    return chat_session


def get_user_chat_session(
    session_id: uuid.UUID,
    owner_id: uuid.UUID,
    owner_role: str,
    session: Session,
) -> Optional[ChatSession]:
    query = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.owner_id == owner_id,
        ChatSession.owner_role == owner_role,
        ChatSession.is_delete == False,
    )
    return session.exec(query).first()


def list_user_chat_sessions(
    owner_id: uuid.UUID,
    owner_role: str,
    page: int,
    session: Session,
) -> PaginatedChatSessionResponse:
    page = max(1, page)
    offset_value = (page - 1) * CHAT_SESSION_PAGE_SIZE

    count_query = select(func.count(ChatSession.id)).where(
        ChatSession.owner_id == owner_id,
        ChatSession.owner_role == owner_role,
        ChatSession.is_delete == False,
    )
    total_count = session.exec(count_query).one()

    query = (
        select(ChatSession)
        .where(
            ChatSession.owner_id == owner_id,
            ChatSession.owner_role == owner_role,
            ChatSession.is_delete == False,
        )
        .order_by(ChatSession.updated_at.desc())
        .offset(offset_value)
        .limit(CHAT_SESSION_PAGE_SIZE)
    )
    sessions = session.exec(query).all()

    rows: list[ChatSessionResponse] = []
    for chat_session in sessions:
        msg_count = session.exec(
            select(func.count(ChatMessage.id)).where(ChatMessage.session_id == chat_session.id)
        ).one()

        last_message = session.exec(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.created_at.desc())
        ).first()

        rows.append(
            ChatSessionResponse(
                id=chat_session.id,
                title=chat_session.title,
                message_count=msg_count,
                last_message_preview=(last_message.content[:120] if last_message else None),
                created_at=chat_session.created_at,
                updated_at=chat_session.updated_at,
            )
        )

    total_pages = max(1, (total_count + CHAT_SESSION_PAGE_SIZE - 1) // CHAT_SESSION_PAGE_SIZE)

    return PaginatedChatSessionResponse(
        data=rows,
        total_count=total_count,
        page=page,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


def append_chat_message(
    chat_session: ChatSession,
    role: str,
    content: str,
    session: Session,
) -> ChatMessage:
    # The chatbot pipeline can execute SQL reads that leave the session in
    # an aborted transaction state on DB errors. Clear it before persisting.
    session.rollback()

    persisted_session = session.get(ChatSession, chat_session.id)
    if not persisted_session:
        raise ValueError("Chat session not found while appending message")

    message = ChatMessage(
        session_id=persisted_session.id,
        role=role,
        content=content,
    )
    persisted_session.updated_at = datetime.now()

    # Auto-title from the first user message so the history list is easier to scan.
    if role == "user" and (persisted_session.title or "").strip().lower() == "new chat":
        persisted_session.title = content.strip()[:60] or "New Chat"

    session.add(message)
    session.add(persisted_session)
    session.commit()
    session.refresh(message)
    return message


def get_chat_session_detail(chat_session: ChatSession, session: Session) -> ChatSessionDetailResponse:
    query = (
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = session.exec(query).all()

    return ChatSessionDetailResponse(
        id=chat_session.id,
        title=chat_session.title,
        created_at=chat_session.created_at,
        updated_at=chat_session.updated_at,
        messages=[
            ChatMessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )
