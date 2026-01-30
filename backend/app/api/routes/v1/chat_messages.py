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
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
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
from app.services.langflow import get_langflow_client, LangflowError


logger = logging.getLogger(__name__)

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

    # Validate role
    if message_in.role not in ["user", "assistant"]:
        raise HTTPException(
            status_code=400, detail="Role must be 'user' or 'assistant'"
        )

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

    async def generate_stream() -> AsyncGenerator[str, None]:
        """Generate SSE events from Langflow streaming response."""
        client = get_langflow_client()
        accumulated_content = ""

        try:
            # Stream from Langflow
            async for chunk in client.chat_stream(
                message=request.content,
                session_id=str(chat_id),
            ):
                accumulated_content += chunk
                event = {"type": "content", "content": chunk}
                yield f"data: {json.dumps(event)}\n\n"

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

                # Send done event with message ID
                done_event = {"type": "done", "message_id": assistant_message.id}
                yield f"data: {json.dumps(done_event)}\n\n"
            else:
                # No content received, send done without message_id
                logger.warning(f"No content received from Langflow for chat {chat_id}")
                done_event = {"type": "done"}
                yield f"data: {json.dumps(done_event)}\n\n"

        except LangflowError as e:
            logger.error(f"Langflow error in chat {chat_id}: {e.message}")
            error_event = {"type": "error", "error": e.message}
            yield f"data: {json.dumps(error_event)}\n\n"

        except Exception as e:
            logger.error(f"Unexpected error in chat {chat_id}: {str(e)}")
            error_event = {"type": "error", "error": "An unexpected error occurred"}
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
