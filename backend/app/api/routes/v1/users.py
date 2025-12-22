from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.models import UserPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user info.

    Returns the current authenticated user's information based on
    OAuth proxy headers.
    """
    return current_user
