"""
Job API endpoints for tracking long-running LangFlow executions.

This module provides:
- GET /jobs/{id} — Get job status with optional ?sync=true to poll LangFlow
- POST /jobs/{id}/cancel — Cancel a running job
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.models import Chat, ChatMessage, Job, JobPublic, JobStatus, TERMINAL_STATUSES
from app.services.langflow import get_langflow_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def verify_job_ownership(
    job: Job, current_user: CurrentUser, session: SessionDep
) -> None:
    """
    Verify the current user owns the chat associated with this job.

    Traverses: job -> chat_message -> chat -> user_id
    Admins can access any job.

    Raises:
        HTTPException: 403 if user does not own the job's chat
        HTTPException: 404 if chat_message or chat not found
    """
    chat_message = session.get(ChatMessage, job.chat_message_id)
    if not chat_message:
        raise HTTPException(status_code=404, detail="Job's chat message not found")

    chat = session.get(Chat, chat_message.chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Job's chat not found")

    if chat.user_id != current_user.id and not current_user.admin:
        raise HTTPException(status_code=403, detail="Not enough permissions")


def extract_result_text(outputs: dict) -> str:
    """
    Extract the chat output text from LangFlow V2 response outputs.

    Navigates the V2 output structure to find the message text,
    using the same pattern as the existing chat() method.

    Args:
        outputs: The 'outputs' dict from V2 workflow status response

    Returns:
        The extracted text, or empty string if not found
    """
    try:
        output_list = outputs.get("outputs", [])
        if output_list:
            first_output = output_list[0]
            if "outputs" in first_output:
                inner_outputs = first_output["outputs"]
                if inner_outputs:
                    message_data = inner_outputs[0].get("results", {}).get(
                        "message", {}
                    )
                    return message_data.get("text", "")
    except (IndexError, AttributeError, TypeError):
        logger.warning("Failed to extract result text from V2 outputs")
    return ""


async def sync_job_status_with_langflow(
    job: Job, session: SessionDep
) -> None:
    """
    Sync job status with LangFlow V2 API. Skip for terminal states.

    Called when GET /jobs/{id}?sync=true. Polls LangFlow for the latest
    status and updates our database record.

    Args:
        job: The Job record to sync
        session: Database session
    """
    if not job.langflow_job_id:
        return
    if job.status in {s.value for s in TERMINAL_STATUSES}:
        return

    try:
        client = get_langflow_client()
        lf_response = await client.get_workflow_status(job.langflow_job_id)
        lf_status = lf_response.get("status", "").lower()

        STATUS_MAP = {
            "queued": JobStatus.PENDING,
            "pending": JobStatus.PENDING,
            "in_progress": JobStatus.IN_PROGRESS,
            "running": JobStatus.IN_PROGRESS,
            "completed": JobStatus.COMPLETED,
            "success": JobStatus.COMPLETED,
            "failed": JobStatus.FAILED,
            "error": JobStatus.FAILED,
            "cancelled": JobStatus.CANCELLED,
            "canceled": JobStatus.CANCELLED,
            "timed_out": JobStatus.TIMED_OUT,
        }

        new_status = STATUS_MAP.get(lf_status)
        if new_status and new_status.value != job.status:
            job.status = new_status.value
            now = datetime.now(timezone.utc)

            if new_status == JobStatus.IN_PROGRESS and not job.started_at:
                job.started_at = now

            if new_status == JobStatus.COMPLETED:
                job.result_content = extract_result_text(
                    lf_response.get("outputs", {})
                )
                job.completed_at = now
            elif new_status in (JobStatus.FAILED, JobStatus.TIMED_OUT):
                errors = lf_response.get("errors", [])
                if errors and isinstance(errors[0], dict):
                    job.error_message = errors[0].get("error", "Unknown error")
                else:
                    job.error_message = lf_response.get("error", "Unknown error")
                job.completed_at = now

            job.updated_at = now
            session.add(job)
            session.commit()
            session.refresh(job)

    except Exception as e:
        logger.warning(f"Error syncing job {job.id} with LangFlow: {e}")


@router.get("/{job_id}", response_model=JobPublic)
async def get_job(
    job_id: int,
    sync: bool = False,
    session: SessionDep = None,
    current_user: CurrentUser = None,
) -> Job:
    """
    Get job status.

    If sync=true, poll LangFlow V2 API first and update our record
    before returning. This is the primary mechanism for frontend polling.
    """
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    verify_job_ownership(job, current_user, session)

    if sync:
        await sync_job_status_with_langflow(job, session)

    return job


@router.post("/{job_id}/cancel", response_model=JobPublic)
async def cancel_job(
    job_id: int,
    session: SessionDep = None,
    current_user: CurrentUser = None,
) -> Job:
    """
    Cancel a running job by calling LangFlow V2 stop endpoint.

    Returns 400 if the job is already in a terminal state.
    """
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    verify_job_ownership(job, current_user, session)

    if job.status in {s.value for s in TERMINAL_STATUSES}:
        raise HTTPException(status_code=400, detail="Job already in terminal state")

    client = get_langflow_client()
    if job.langflow_job_id:
        try:
            await client.stop_workflow(job.langflow_job_id)
        except Exception as e:
            logger.warning(f"Failed to stop LangFlow workflow for job {job.id}: {e}")

    now = datetime.now(timezone.utc)
    job.status = JobStatus.CANCELLED.value
    job.completed_at = now
    job.updated_at = now
    session.add(job)
    session.commit()
    session.refresh(job)
    return job
