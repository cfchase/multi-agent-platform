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

# HTTP timeout constants (seconds)
LIST_FLOWS_TIMEOUT = 30.0
CHAT_TIMEOUT = 120.0

# SSE constants
SSE_DATA_PREFIX = "data: "
SSE_DONE_MARKER = "[DONE]"


def extract_chunk_from_sse_data(data: dict) -> str | None:
    """
    Extract the text chunk from an SSE data payload.

    Handles multiple Langflow streaming formats:
    - Token event: {"event": "token", "data": {"chunk": "..."}}
    - Add message event: {"event": "add_message", "data": {"text": "...", "sender": "Machine"}}
    - Direct chunk: {"chunk": "..."}

    For add_message events, only extracts text from AI/Machine responses (not user messages).

    Returns the chunk text or None if not found.
    """
    event_type = data.get("event")

    if event_type == "token":
        return data.get("data", {}).get("chunk") or None

    if event_type == "add_message":
        # Only extract text from AI/Machine responses, not user messages
        event_data = data.get("data", {})
        sender = event_data.get("sender", "")
        if sender in ("Machine", "AI"):
            return event_data.get("text") or None
        return None

    if "chunk" in data:
        return data.get("chunk") or None

    return None


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
    - LANGFLOW_DEFAULT_FLOW: Default flow name to execute (optional)
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        langflow_id: str | None = None,
        default_flow: str | None = None,
    ):
        """
        Initialize Langflow client.

        Args:
            base_url: Langflow server URL (defaults to settings.LANGFLOW_URL)
            api_key: API key for authentication (defaults to settings.LANGFLOW_API_KEY)
            langflow_id: Langflow project ID (defaults to settings.LANGFLOW_ID)
            default_flow: Default flow name (defaults to settings.LANGFLOW_DEFAULT_FLOW)
        """
        self.base_url = base_url or settings.LANGFLOW_URL
        self.api_key = api_key or settings.LANGFLOW_API_KEY
        self.langflow_id = langflow_id or settings.LANGFLOW_ID
        self.default_flow = default_flow or settings.LANGFLOW_DEFAULT_FLOW

        # Cache for flow name to ID mapping
        self._flow_cache: dict[str, str] = {}

        # Build headers
        self.headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            self.headers["x-api-key"] = self.api_key

    async def get_flow_id_by_name(self, name: str) -> str | None:
        """
        Look up a flow ID by its name.

        Args:
            name: The flow name to look up

        Returns:
            The flow ID if found, None otherwise
        """
        # Check cache first
        if name in self._flow_cache:
            return self._flow_cache[name]

        # Fetch flows and find by name
        flows = await self.list_flows()
        for flow in flows:
            self._flow_cache[flow.name] = flow.id
            if flow.name == name:
                return flow.id

        return None

    async def resolve_flow_id(
        self, flow_id: str | None = None, flow_name: str | None = None
    ) -> str | None:
        """
        Resolve a flow ID from either an ID or name.

        Priority:
        1. Explicit flow_id parameter
        2. Explicit flow_name parameter (looked up)
        3. Configured default_flow setting (looked up)

        Args:
            flow_id: Optional explicit flow ID
            flow_name: Optional explicit flow name

        Returns:
            The resolved flow ID, or None if not found
        """
        # If explicit ID provided, use it
        if flow_id:
            return flow_id

        # If explicit name provided, look it up
        if flow_name:
            resolved = await self.get_flow_id_by_name(flow_name)
            if resolved:
                return resolved

        # Fall back to configured default flow name
        if self.default_flow:
            resolved = await self.get_flow_id_by_name(self.default_flow)
            if resolved:
                return resolved

        return None

    def _get_run_url(self, flow_id: str, stream: bool = False) -> str:
        """
        Build the Langflow run API URL.

        Args:
            flow_id: The flow ID to execute (required)
            stream: Whether to use streaming endpoint

        Returns:
            Full URL for the Langflow run API
        """
        if self.langflow_id:
            # Langflow Cloud format
            base = f"{self.base_url}/lf/{self.langflow_id}/api/v1/run/{flow_id}"
        else:
            # Self-hosted Langflow format
            base = f"{self.base_url}/api/v1/run/{flow_id}"

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

        async with httpx.AsyncClient(timeout=LIST_FLOWS_TIMEOUT) as client:
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
        flow_name: str | None = None,
    ) -> str:
        """
        Send a chat message and get a response (non-streaming).

        Args:
            message: The user message to send
            session_id: Optional session ID for conversation continuity
            tweaks: Optional tweaks to modify flow behavior
            flow_id: Optional flow ID to use (defaults to configured flow)
            flow_name: Optional flow name to use (looked up to get ID)

        Returns:
            The assistant's response text

        Raises:
            LangflowError: If the API call fails
        """
        # Resolve flow ID from name if needed
        resolved_flow_id = await self.resolve_flow_id(flow_id, flow_name)
        if not resolved_flow_id:
            raise LangflowError("No flow ID or name configured")

        payload = {
            "input_value": message,
            "output_type": "chat",
            "input_type": "chat",
        }

        if session_id:
            payload["session_id"] = session_id
        if tweaks:
            payload["tweaks"] = tweaks

        url = self._get_run_url(flow_id=resolved_flow_id, stream=False)

        async with httpx.AsyncClient(timeout=CHAT_TIMEOUT) as client:
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
        flow_name: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Send a chat message and stream the response.

        Args:
            message: The user message to send
            session_id: Optional session ID for conversation continuity
            tweaks: Optional tweaks to modify flow behavior
            flow_id: Optional flow ID to use (defaults to configured flow)
            flow_name: Optional flow name to use (looked up to get ID)

        Yields:
            Chunks of the assistant's response text

        Raises:
            LangflowError: If the API call fails
        """
        # Resolve flow ID from name if needed
        resolved_flow_id = await self.resolve_flow_id(flow_id, flow_name)
        if not resolved_flow_id:
            raise LangflowError("No flow ID or name configured")

        payload = {
            "input_value": message,
            "output_type": "chat",
            "input_type": "chat",
        }

        if session_id:
            payload["session_id"] = session_id
        if tweaks:
            payload["tweaks"] = tweaks

        url = self._get_run_url(flow_id=resolved_flow_id, stream=True)

        async with httpx.AsyncClient(timeout=CHAT_TIMEOUT) as client:
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
                        if line.startswith(SSE_DATA_PREFIX):
                            data_str = line[len(SSE_DATA_PREFIX):]
                            if data_str == SSE_DONE_MARKER:
                                break
                        else:
                            # Handle plain JSON format from Langflow
                            data_str = line

                        try:
                            data = json.loads(data_str)
                            chunk = extract_chunk_from_sse_data(data)
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            # Log malformed JSON for debugging, but continue processing
                            # (some SSE lines like event markers may not be JSON)
                            logger.debug(f"Non-JSON SSE line received: {data_str[:100]}")
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
