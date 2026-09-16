"""
Jobs REST API routes for polling async Celery task status.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from celery.result import AsyncResult

from packages.auth.dependencies import CurrentUser, require_role
from apps.worker.tasks.reports import generate_inventory_report, generate_sales_report
from apps.worker.tasks.imports import bulk_import_products
from apps.worker.tasks.agent_runs import run_agent_async

router = APIRouter(prefix="/jobs", tags=["Async Jobs"])


class EnqueueReportRequest(BaseModel):
    report_type: str  # "inventory" or "sales"


class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None


@router.post("/reports", response_model=JobResponse)
async def enqueue_report_job(
    body: EnqueueReportRequest,
    current_user: CurrentUser,
):
    if body.report_type == "inventory":
        task = generate_inventory_report.delay(str(current_user.org_id))
    elif body.report_type == "sales":
        task = generate_sales_report.delay(str(current_user.org_id))
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown report type '{body.report_type}'")

    return JobResponse(
        job_id=task.id,
        status="queued",
        message=f"{body.report_type.capitalize()} report job queued successfully",
    )


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    current_user: CurrentUser,
):
    task_result = AsyncResult(job_id)
    state = task_result.state

    if state == "SUCCESS":
        return JobStatusResponse(job_id=job_id, status=state, result=task_result.result)
    elif state == "FAILURE":
        return JobStatusResponse(job_id=job_id, status=state, error=str(task_result.info))
    else:
        return JobStatusResponse(job_id=job_id, status=state)
