"""
Chat Messages API endpoints.

This module provides operations for chat messages:
- List messages in a chat
- Create new message
- Stream AI response via SSE
- Delete message
"""

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
    build_app_tweaks,
    build_flow_tweaks,
    get_required_services_for_flow,
    MissingTokenError,
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

    # Save user message
    user_message = ChatMessage(
        chat_id=chat_id,
        content=request.content,
        role="user",
    )
    session.add(user_message)

    # Update chat's updated_at timestamp
    chat.updated_at = datetime.now(timezone.utc)
    session.add(chat)
    session.commit()
    session.refresh(user_message)

    # Build tweaks: application-level API keys + user OAuth tokens
    flow_name = request.flow_name or settings.LANGFLOW_DEFAULT_FLOW

    # Application-level tweaks (API keys from backend config)
    tweaks = build_app_tweaks(flow_name) if flow_name else None

    # User-level tweaks (OAuth tokens from database)
    token_config = get_required_services_for_flow(flow_name) if flow_name else {}
    if token_config:
        try:
            tweaks = await build_flow_tweaks(
                session=session,
                user_id=current_user.id,
                token_config=token_config,
                existing_tweaks=tweaks,
            )
        except MissingTokenError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Missing integration: {e.service_name}. "
                       "Please connect the service in Settings.",
            )

    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate SSE events from Langflow streaming response."""
        client = get_langflow_client()
        accumulated_content = ""

        try:
            # Stream from Langflow
            async for chunk in client.chat_stream(
                message=request.content,
                session_id=str(chat_id),
                flow_id=request.flow_id,
                flow_name=request.flow_name,
                tweaks=tweaks,
            ):
                accumulated_content += chunk
                yield format_sse_event({"type": "content", "content": chunk})

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
                yield format_sse_event({"type": "done"})

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
