"""
Job model and related schemas.

This module contains:
- JobStatus enum for job lifecycle states
- TERMINAL_STATUSES set for completed states
- Job database model (table=True)
- JobPublic: Output schema for API responses
"""

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.chat_message import ChatMessage


class JobStatus(str, Enum):
    """Job lifecycle states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


TERMINAL_STATUSES = {
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
    JobStatus.TIMED_OUT,
}


class Job(SQLModel, table=True):
    """Job database model for tracking long-running LangFlow executions."""
    __tablename__ = "job"

    id: int | None = Field(default=None, primary_key=True)
    chat_message_id: int = Field(
        foreign_key="chat_message.id", nullable=False, index=True, ondelete="CASCADE"
    )
    langflow_job_id: str | None = Field(
        default=None, index=True, max_length=255
    )
    flow_id: str | None = Field(default=None, max_length=255)
    status: str = Field(default=JobStatus.PENDING, max_length=50, index=True)
    error_message: str | None = Field(
        default=None, sa_column=Column("error_message", Text, nullable=True)
    )
    result_content: str | None = Field(
        default=None, sa_column=Column("result_content", Text, nullable=True)
    )
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_type=DateTime(timezone=True),
    )

    # Relationship back to ChatMessage
    chat_message: Optional["ChatMessage"] = Relationship(back_populates="job")


class JobPublic(SQLModel):
    """Properties to return via API."""
    id: int
    chat_message_id: int
    langflow_job_id: str | None
    flow_id: str | None
    status: str
    error_message: str | None
    result_content: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
