"""
Chat API endpoints.

This module provides CRUD operations for chats:
- List chats for current user
- Get chat by ID
- Create new chat
- Update chat
- Delete chat
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Chat,
    ChatCreate,
    ChatPublic,
    ChatsPublic,
    ChatUpdate,
    Message,
)

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("/", response_model=ChatsPublic)
def read_chats(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve chats for the current user.

    Returns all chats owned by the current user with pagination.
    """
    # Build query for user's chats
    statement = select(Chat).where(Chat.user_id == current_user.id)

    # Get count before pagination
    count_statement = select(func.count()).select_from(statement.subquery())
    count = session.exec(count_statement).one()

    # Apply ordering and pagination
    statement = statement.order_by(Chat.updated_at.desc())
    statement = statement.offset(skip).limit(limit)
    chats = session.exec(statement).all()

    return ChatsPublic(data=chats, count=count)


@router.get("/{id}", response_model=ChatPublic)
def read_chat(session: SessionDep, current_user: CurrentUser, id: int) -> Any:
    """
    Get chat by ID.

    Users can only view their own chats (unless admin).
    """
    chat = session.get(Chat, id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Check ownership (admins can view any chat)
    if chat.user_id != current_user.id and not current_user.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return chat


@router.post("/", response_model=ChatPublic)
def create_chat(
    *, session: SessionDep, current_user: CurrentUser, chat_in: ChatCreate
) -> Any:
    """
    Create new chat.

    The chat is associated with the current authenticated user.
    """
    chat = Chat.model_validate(chat_in, update={"user_id": current_user.id})
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return chat


@router.put("/{id}", response_model=ChatPublic)
def update_chat(
    *, session: SessionDep, current_user: CurrentUser, id: int, chat_in: ChatUpdate
) -> Any:
    """
    Update a chat.

    Users can only update their own chats (unless admin).
    """
    chat = session.get(Chat, id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Check ownership (admins can update any chat)
    if chat.user_id != current_user.id and not current_user.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_dict = chat_in.model_dump(exclude_unset=True)
    update_dict["updated_at"] = datetime.now(timezone.utc)
    chat.sqlmodel_update(update_dict)
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return chat


@router.delete("/{id}")
def delete_chat(session: SessionDep, current_user: CurrentUser, id: int) -> Message:
    """
    Delete a chat.

    Users can only delete their own chats (unless admin).
    This will also delete all messages in the chat (cascade).
    """
    chat = session.get(Chat, id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Check ownership (admins can delete any chat)
    if chat.user_id != current_user.id and not current_user.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    session.delete(chat)
    session.commit()
    return Message(message="Chat deleted successfully")
