"""
Chat Messages API endpoints.

This module provides operations for chat messages:
- List messages in a chat
- Create new message
- Stream AI response via SSE
- Delete message
"""

import asyncio
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Chat,
    ChatMessage,
    ChatMessageCreate,
    ChatMessagePublic,
    ChatMessagesPublic,
    Message,
)
from app.core.config import settings
from app.services.flow_token_injection import (
    build_app_settings_data,
    build_generic_tweaks,
    build_user_settings_data,
)
from app.services.langflow import LangflowError, get_langflow_client

logger = logging.getLogger(__name__)

# SSE response headers
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # Disable nginx buffering
}


def format_sse_event(event_data: dict) -> str:
    """Format a dictionary as an SSE event string."""
    return f"data: {json.dumps(event_data)}\n\n"

router = APIRouter(prefix="/chats/{chat_id}/messages", tags=["chat-messages"])


def get_chat_with_permission(
    session: SessionDep, current_user: CurrentUser, chat_id: int
) -> Chat:
    """
    Helper to get chat and verify user has access.

    Raises HTTPException if chat not found or user lacks permission.
    """
    chat = session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Check ownership (admins can access any chat)
    if chat.user_id != current_user.id and not current_user.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return chat


@router.get("/", response_model=ChatMessagesPublic)
def read_messages(
    session: SessionDep,
    current_user: CurrentUser,
    chat_id: int,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve messages for a chat.

    Returns all messages in the chat with pagination.
    Messages are ordered by created_at ascending (oldest first).
    """
    # Verify chat exists and user has access
    get_chat_with_permission(session, current_user, chat_id)

    # Build query for chat messages
    statement = select(ChatMessage).where(ChatMessage.chat_id == chat_id)

    # Get count before pagination
    count_statement = select(func.count()).select_from(statement.subquery())
    count = session.exec(count_statement).one()

    # Apply ordering and pagination (id is auto-increment, guarantees insertion order)
    statement = statement.order_by(ChatMessage.id.asc())
    statement = statement.offset(skip).limit(limit)
    messages = session.exec(statement).all()

    return ChatMessagesPublic(data=messages, count=count)


@router.post("/", response_model=ChatMessagePublic)
def create_message(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    chat_id: int,
    message_in: ChatMessageCreate,
) -> Any:
    """
    Create new message in a chat.

    The message is associated with the specified chat.
    Only the chat owner (or admin) can add messages.
    """
    # Verify chat exists and user has access
    get_chat_with_permission(session, current_user, chat_id)

    # Role is validated by Pydantic via MessageRole Literal type
    message = ChatMessage.model_validate(message_in, update={"chat_id": chat_id})
    session.add(message)
    session.commit()
    session.refresh(message)
    return message


@router.delete("/{message_id}")
def delete_message(
    session: SessionDep,
    current_user: CurrentUser,
    chat_id: int,
    message_id: int,
) -> Message:
    """
    Delete a message from a chat.

    Only the chat owner (or admin) can delete messages.
    """
    # Verify chat exists and user has access
    get_chat_with_permission(session, current_user, chat_id)

    # Get the message
    chat_message = session.get(ChatMessage, message_id)
    if not chat_message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Verify message belongs to the chat
    if chat_message.chat_id != chat_id:
        raise HTTPException(status_code=404, detail="Message not found in this chat")

    session.delete(chat_message)
    session.commit()
    return Message(message="Message deleted successfully")


class StreamMessageRequest(BaseModel):
    """Request body for streaming message endpoint."""
    content: str
    flow_id: str | None = None
    flow_name: str | None = None


@router.post("/stream")
async def stream_message(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    chat_id: int,
    request: StreamMessageRequest,
) -> StreamingResponse:
    """
    Send a message and stream the AI response.

    This endpoint:
    1. Saves the user message to the database
    2. Sends it to Langflow for processing
    3. Streams the response back as SSE events
    4. Saves the complete response as an assistant message

    SSE Event format:
    - data: {"type": "content", "content": "chunk text"}
    - data: {"type": "done", "message_id": 123}
    - data: {"type": "error", "error": "error message"}
    """
    # Verify chat exists and user has access
    chat = get_chat_with_permission(session, current_user, chat_id)

    # Resolve flow name
    flow_name = request.flow_name or settings.LANGFLOW_DEFAULT_FLOW

    # Save user message
    user_message = ChatMessage(
        chat_id=chat_id,
        content=request.content,
        role="user",
    )
    session.add(user_message)

    # Update chat's updated_at timestamp
    chat.updated_at = datetime.now(timezone.utc)

    # Lock flow to chat on first message
    if not chat.flow_name and flow_name:
        chat.flow_name = flow_name

    session.add(chat)
    session.commit()
    session.refresh(user_message)

    # Build user data with all available OAuth tokens
    user_data = await build_user_settings_data(
        session=session,
        user_id=current_user.id,
    )

    # Build app data (feature flags, config)
    app_data = build_app_settings_data()

    # Always send generic tweaks - flows opt in via components
    tweaks = build_generic_tweaks(user_data=user_data, app_data=app_data)

    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate SSE events from Langflow streaming response.

        Sends periodic SSE heartbeat comments while waiting for LangFlow
        to prevent proxies (nginx, OAuth proxy, OpenShift Route) from
        closing the idle chunked connection.
        """
        client = get_langflow_client()
        accumulated_content = ""

        # Send initial heartbeat immediately to establish the chunked stream
        # (SSE comment — ignored by EventSource clients but keeps proxies alive)
        yield ": heartbeat\n\n"

        try:
            # Use an async queue so we can interleave heartbeats with real data
            chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()

            async def langflow_producer():
                """Read from LangFlow and put chunks on the queue."""
                try:
                    async for chunk in client.chat_stream(
                        message=request.content,
                        session_id=str(chat_id),
                        flow_id=request.flow_id,
                        flow_name=request.flow_name,
                        tweaks=tweaks,
                    ):
                        await chunk_queue.put(chunk)
                finally:
                    await chunk_queue.put(None)  # sentinel

            producer_task = asyncio.create_task(langflow_producer())

            try:
                while True:
                    try:
                        chunk = await asyncio.wait_for(
                            chunk_queue.get(), timeout=15.0
                        )
                    except asyncio.TimeoutError:
                        # No data from LangFlow yet — send heartbeat to keep alive
                        yield ": heartbeat\n\n"
                        continue

                    if chunk is None:
                        break  # stream finished
                    accumulated_content += chunk
                    yield format_sse_event({"type": "content", "content": chunk})
            finally:
                if not producer_task.done():
                    producer_task.cancel()
                    try:
                        await producer_task
                    except (asyncio.CancelledError, Exception):
                        pass
                # Re-raise any exception from the producer
                if producer_task.done() and not producer_task.cancelled():
                    exc = producer_task.exception()
                    if exc:
                        raise exc

            # Save assistant message with accumulated content (only if not empty)
            if accumulated_content.strip():
                assistant_message = ChatMessage(
                    chat_id=chat_id,
                    content=accumulated_content,
                    role="assistant",
                )
                session.add(assistant_message)
                session.commit()
                session.refresh(assistant_message)

                yield format_sse_event({"type": "done", "message_id": assistant_message.id})
            else:
                logger.warning(f"No content received from Langflow for chat {chat_id}")
                yield format_sse_event({
                    "type": "error",
                    "error": "No response received from the AI service. "
                             "The query may have been rejected by the flow.",
                })

        except LangflowError as e:
            logger.error(f"Langflow error in chat {chat_id}: {e.message}")
            yield format_sse_event({"type": "error", "error": e.message})

        except SQLAlchemyError as e:
            logger.error(
                f"Database error in chat {chat_id}: {type(e).__name__}: {str(e)}"
            )
            yield format_sse_event({"type": "error", "error": "Database error occurred"})

        except Exception as e:
            # Log full traceback for debugging unexpected errors
            logger.error(
                f"Unexpected error in chat {chat_id}: {type(e).__name__}: {str(e)}\n"
                f"{traceback.format_exc()}"
            )
            yield format_sse_event({"type": "error", "error": "An unexpected error occurred"})

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
