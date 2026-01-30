"""
Langflow client for AI chat integration.

This module provides:
- LangflowClient: HTTP client for Langflow API with streaming support
- SSE streaming for real-time chat responses
"""

import json
import logging
from typing import AsyncGenerator

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


class LangflowError(Exception):
    """Exception raised for Langflow API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class Flow:
    """Represents a Langflow flow."""

    def __init__(self, id: str, name: str, description: str | None = None):
        self.id = id
        self.name = name
        self.description = description

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }


class LangflowClient:
    """
    HTTP client for Langflow API integration.

    Supports both synchronous and streaming chat completions.

    Configuration is read from environment variables:
    - LANGFLOW_URL: Base URL of the Langflow server
    - LANGFLOW_API_KEY: API key for authentication (optional for self-hosted)
    - LANGFLOW_ID: Langflow project ID (for Langflow Cloud)
    - LANGFLOW_FLOW_ID: Flow ID to execute
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        langflow_id: str | None = None,
        flow_id: str | None = None,
    ):
        """
        Initialize Langflow client.

        Args:
            base_url: Langflow server URL (defaults to settings.LANGFLOW_URL)
            api_key: API key for authentication (defaults to settings.LANGFLOW_API_KEY)
            langflow_id: Langflow project ID (defaults to settings.LANGFLOW_ID)
            flow_id: Flow ID to use (defaults to settings.LANGFLOW_FLOW_ID)
        """
        self.base_url = base_url or settings.LANGFLOW_URL
        self.api_key = api_key or settings.LANGFLOW_API_KEY
        self.langflow_id = langflow_id or settings.LANGFLOW_ID
        self.flow_id = flow_id or settings.LANGFLOW_FLOW_ID

        # Build headers
        self.headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    def _get_run_url(self, flow_id: str | None = None, stream: bool = False) -> str:
        """
        Build the Langflow run API URL.

        Args:
            flow_id: Override flow ID (defaults to self.flow_id)
            stream: Whether to use streaming endpoint

        Returns:
            Full URL for the Langflow run API
        """
        target_flow_id = flow_id or self.flow_id
        if self.langflow_id:
            # Langflow Cloud format
            base = f"{self.base_url}/lf/{self.langflow_id}/api/v1/run/{target_flow_id}"
        else:
            # Self-hosted Langflow format
            base = f"{self.base_url}/api/v1/run/{target_flow_id}"

        if stream:
            return f"{base}?stream=true"
        return base

    async def list_flows(self) -> list[Flow]:
        """
        List available public flows from Langflow.

        Returns:
            List of Flow objects

        Raises:
            LangflowError: If the API call fails
        """
        if self.langflow_id:
            # Langflow Cloud format
            url = f"{self.base_url}/lf/{self.langflow_id}/api/v1/flows/"
        else:
            # Self-hosted Langflow format
            url = f"{self.base_url}/api/v1/flows/"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self.headers)
                response.raise_for_status()

                data = response.json()
                flows = []

                # Handle both list response and paginated response
                flow_list = data if isinstance(data, list) else data.get("flows", [])

                for flow_data in flow_list:
                    # Filter to only public flows (if access_type field exists)
                    # Langflow returns uppercase (e.g., "PUBLIC", "PRIVATE")
                    access_type = flow_data.get("access_type", "PUBLIC")
                    if access_type.upper() == "PUBLIC":
                        flows.append(
                            Flow(
                                id=flow_data.get("id"),
                                name=flow_data.get("name", "Unnamed Flow"),
                                description=flow_data.get("description"),
                            )
                        )

                return flows

            except httpx.HTTPStatusError as e:
                logger.error(f"Langflow API error listing flows: {e.response.status_code}")
                raise LangflowError(
                    f"Failed to list flows: {e.response.text}",
                    status_code=e.response.status_code,
                )
            except httpx.RequestError as e:
                logger.error(f"Langflow connection error: {e}")
                raise LangflowError(f"Failed to connect to Langflow: {str(e)}")

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        tweaks: dict | None = None,
        flow_id: str | None = None,
    ) -> str:
        """
        Send a chat message and get a response (non-streaming).

        Args:
            message: The user message to send
            session_id: Optional session ID for conversation continuity
            tweaks: Optional tweaks to modify flow behavior
            flow_id: Optional flow ID to use (defaults to configured flow)

        Returns:
            The assistant's response text

        Raises:
            LangflowError: If the API call fails
        """
        payload = {
            "input_value": message,
            "output_type": "chat",
            "input_type": "chat",
        }

        if session_id:
            payload["session_id"] = session_id
        if tweaks:
            payload["tweaks"] = tweaks

        url = self._get_run_url(flow_id=flow_id, stream=False)

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self.headers,
                )
                response.raise_for_status()

                data = response.json()
                # Extract the message from Langflow response
                outputs = data.get("outputs", [])
                if outputs:
                    # Navigate to the message text
                    first_output = outputs[0]
                    if "outputs" in first_output:
                        inner_outputs = first_output["outputs"]
                        if inner_outputs:
                            message_data = inner_outputs[0].get("results", {}).get(
                                "message", {}
                            )
                            return message_data.get("text", "")

                return ""

            except httpx.HTTPStatusError as e:
                logger.error(f"Langflow API error: {e.response.status_code} - {e.response.text}")
                raise LangflowError(
                    f"Langflow API error: {e.response.text}",
                    status_code=e.response.status_code,
                )
            except httpx.RequestError as e:
                logger.error(f"Langflow connection error: {e}")
                raise LangflowError(f"Failed to connect to Langflow: {str(e)}")

    async def chat_stream(
        self,
        message: str,
        session_id: str | None = None,
        tweaks: dict | None = None,
        flow_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send a chat message and stream the response.

        Args:
            message: The user message to send
            session_id: Optional session ID for conversation continuity
            tweaks: Optional tweaks to modify flow behavior
            flow_id: Optional flow ID to use (defaults to configured flow)

        Yields:
            Chunks of the assistant's response text

        Raises:
            LangflowError: If the API call fails
        """
        payload = {
            "input_value": message,
            "output_type": "chat",
            "input_type": "chat",
        }

        if session_id:
            payload["session_id"] = session_id
        if tweaks:
            payload["tweaks"] = tweaks

        url = self._get_run_url(flow_id=flow_id, stream=True)

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    headers=self.headers,
                ) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        # Handle SSE format (data: {...})
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix
                            if data_str == "[DONE]":
                                break
                        else:
                            # Handle plain JSON format from Langflow
                            data_str = line

                        try:
                            data = json.loads(data_str)

                            # Langflow streaming format: {"event": "token", "data": {"chunk": "..."}}
                            if data.get("event") == "token":
                                chunk = data.get("data", {}).get("chunk", "")
                                if chunk:
                                    yield chunk
                            # Also handle direct chunk format: {"chunk": "..."}
                            elif "chunk" in data:
                                chunk = data.get("chunk", "")
                                if chunk:
                                    yield chunk
                        except json.JSONDecodeError:
                            # Some lines might not be JSON
                            continue

            except httpx.HTTPStatusError as e:
                logger.error(f"Langflow streaming error: {e.response.status_code}")
                raise LangflowError(
                    f"Langflow streaming error: {e.response.text}",
                    status_code=e.response.status_code,
                )
            except httpx.RequestError as e:
                logger.error(f"Langflow connection error: {e}")
                raise LangflowError(f"Failed to connect to Langflow: {str(e)}")
