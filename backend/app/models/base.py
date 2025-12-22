"""
Shared base models and utilities.

This module contains:
- Generic response models (Message)
- Any shared mixins or base classes used across multiple models
"""

from sqlmodel import SQLModel


class Message(SQLModel):
    """Generic message response model."""
    message: str
