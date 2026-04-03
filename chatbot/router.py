import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from deps import AllUser, UserRole
from schemas import ChatRequest
from chatbot.rag_engine import run_agent_stream
from chatbot.telemetry import create_request_id, log_event
from core.database import SessionDep

router = APIRouter(
    prefix="/chatbot",
)


@router.post("/chat")
async def chat(request: ChatRequest, current_user: AllUser, session: SessionDep):
    """
    SSE endpoint — streams LLM response token by token.
    Frontend reads this as a stream, not a single response.
    """
    user, role = current_user
    request_id = create_request_id()

    async def event_stream():
        try:
            # Send a start event so frontend knows stream began
            yield f"data: {json.dumps({'type': 'start', 'request_id': request_id})}\n\n"

            if role == UserRole.PARENT:
                student_ids = {}
                for i, student in enumerate(user.students):
                    student_ids[i] = student.id

                # Stream tokens from the agent
                async for token in run_agent_stream(
                        query=request.query,
                        role=role,
                        user_id=user.id,
                        extra=student_ids,
                        session=session,
                        chat_history=request.chat_history,
                        request_id=request_id,
                ):
                    payload: str
                    if isinstance(token, dict):
                        payload = json.dumps(token)
                    else:
                        payload = json.dumps({"type": "token", "value": token})
                    yield f"data: {payload}\n\n"
                    await asyncio.sleep(0)  # yield control to event loop
            else:
                # Stream tokens from the agent
                async for token in run_agent_stream(
                        query=request.query,
                        role=role,
                        user_id=user.id,
                        session=session,
                        chat_history=request.chat_history,
                        request_id=request_id,
                ):
                    payload: str
                    if isinstance(token, dict):
                        payload = json.dumps(token)
                    else:
                        payload = json.dumps({"type": "token", "value": token})
                    yield f"data: {payload}\n\n"
                    await asyncio.sleep(0)  # yield control to event loop

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
