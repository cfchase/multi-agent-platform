"""
Flows API endpoints.

This module provides operations for listing available Langflow flows.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.config import settings
from app.services.langflow import get_langflow_client, LangflowError


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/flows", tags=["flows"])


class FlowPublic(BaseModel):
    """Public flow representation."""

    id: str
    name: str
    description: str | None = None


class FlowsPublic(BaseModel):
    """Response containing list of flows."""

    data: list[FlowPublic]
    count: int
    default_flow: str | None = None


@router.get("/", response_model=FlowsPublic)
async def list_flows(
    current_user: CurrentUser,
) -> Any:
    """
    List available public flows from Langflow.

    Returns a list of flows that can be used for chat.
    """
    client = get_langflow_client()

    try:
        flows = await client.list_flows()
        flow_list = [
            FlowPublic(
                id=flow.id,
                name=flow.name,
                description=flow.description,
            )
            for flow in flows
        ]
        return FlowsPublic(
            data=flow_list,
            count=len(flow_list),
            default_flow=settings.LANGFLOW_DEFAULT_FLOW,
        )

    except LangflowError as e:
        logger.error(f"Failed to list flows: {e.message}")
        raise HTTPException(
            status_code=e.status_code or 500,
            detail=f"Failed to list flows: {e.message}",
        )
