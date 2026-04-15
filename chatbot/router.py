import asyncio
import json
import uuid

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from deps import AllUser, UserRole
from schemas import (
    ChatRequest,
    ChatSessionCreateResponse,
    PaginatedChatSessionResponse,
    ChatSessionDetailResponse,
)
from chatbot.rag_engine import run_agent_stream
from chatbot.telemetry import create_request_id, log_event
from core.database import SessionDep
from repository.chatSession import (
    create_chat_session,
    list_user_chat_sessions,
    get_user_chat_session,
    append_chat_message,
    get_chat_session_detail,
)

router = APIRouter(
    prefix="/chatbot",
)


@router.post("/sessions", response_model=ChatSessionCreateResponse, status_code=201)
def create_session(current_user: AllUser, session: SessionDep):
    user, role = current_user
    created = create_chat_session(owner_id=user.id, owner_role=role, session=session)
    return ChatSessionCreateResponse(session_id=created.id, created_at=created.created_at)


@router.get("/sessions", response_model=PaginatedChatSessionResponse)
def list_sessions(current_user: AllUser, session: SessionDep, page: int = Query(1, ge=1)):
    user, role = current_user
    return list_user_chat_sessions(owner_id=user.id, owner_role=role, page=page, session=session)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
def get_session(session_id: uuid.UUID, current_user: AllUser, session: SessionDep):
    user, role = current_user
    chat_session = get_user_chat_session(
        session_id=session_id,
        owner_id=user.id,
        owner_role=role,
        session=session,
    )
    if not chat_session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return get_chat_session_detail(chat_session=chat_session, session=session)


@router.post("/chat")
async def chat(request: ChatRequest, current_user: AllUser, session: SessionDep):
    """
    SSE endpoint — streams LLM response token by token.
    Frontend reads this as a stream, not a single response.
    """
    user, role = current_user
    request_id = create_request_id()
    chat_session = None

    if request.session_id:
        chat_session = get_user_chat_session(
            session_id=request.session_id,
            owner_id=user.id,
            owner_role=role,
            session=session,
        )
        if not chat_session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        chat_session = create_chat_session(owner_id=user.id, owner_role=role, session=session)

    append_chat_message(
        chat_session=chat_session,
        role="user",
        content=request.query,
        session=session,
    )

    async def event_stream():
        assistant_chunks: list[str] = []
        try:
            # Send a start event so frontend knows stream began
            yield f"data: {json.dumps({'type': 'start', 'request_id': request_id, 'session_id': str(chat_session.id)})}\n\n"

            base_extra = {
                "first_name": getattr(user, "first_name", "") or "",
                "last_name": getattr(user, "last_name", "") or "",
                "display_name": " ".join(
                    part for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part
                ).strip(),
            }

            if role == UserRole.PARENT:
                student_ids = {}
                for i, student in enumerate(user.students):
                    student_ids[i] = student.id

                extra_payload = {**base_extra, "student_ids": student_ids}

                # Stream tokens from the agent
                async for token in run_agent_stream(
                        query=request.query,
                        role=role,
                        user_id=user.id,
                        extra=extra_payload,
                        session=session,
                        chat_history=request.chat_history,
                        request_id=request_id,
                ):
                    payload: str
                    if isinstance(token, dict):
                        if token.get("type") == "token" and token.get("value"):
                            assistant_chunks.append(str(token.get("value")))
                        payload = json.dumps(token)
                    else:
                        assistant_chunks.append(str(token))
                        payload = json.dumps({"type": "token", "value": token})
                    yield f"data: {payload}\n\n"
                    await asyncio.sleep(0)  # yield control to event loop
            else:
                # Stream tokens from the agent
                async for token in run_agent_stream(
                        query=request.query,
                        role=role,
                        user_id=user.id,
                    extra=base_extra,
                        session=session,
                        chat_history=request.chat_history,
                        request_id=request_id,
                ):
                    payload: str
                    if isinstance(token, dict):
                        if token.get("type") == "token" and token.get("value"):
                            assistant_chunks.append(str(token.get("value")))
                        payload = json.dumps(token)
                    else:
                        assistant_chunks.append(str(token))
                        payload = json.dumps({"type": "token", "value": token})
                    yield f"data: {payload}\n\n"
                    await asyncio.sleep(0)  # yield control to event loop

            assistant_message = "".join(assistant_chunks).strip()
            if assistant_message:
                append_chat_message(
                    chat_session=chat_session,
                    role="assistant",
                    content=assistant_message,
                    session=session,
                )

            # Send done event so frontend knows stream ended
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            log_event("stream_error", request_id, error=str(e))
            error_payload = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {error_payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # important for nginx deployments
            "Access-Control-Allow-Origin": "*",
        }
    )
