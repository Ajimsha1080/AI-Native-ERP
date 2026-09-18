"""
Cleanup tasks.

Background tasks for database retention enforcement, temporary file pruning,
session token cleanup, and log rotation.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import os
import gzip
import logging

from celery import shared_task
from sqlalchemy import delete

from packages.database.core import async_session_scope
from packages.database.models import WorkflowExecution, AuditEvent
from packages.database.models.erp.agent_runs import AgentRun
from packages.config import get_settings

logger = logging.getLogger("worker.cleanup")
settings = get_settings()


@shared_task(bind=True, name="cleanup.cleanup_old_executions")
async def cleanup_old_executions_task(
    self,
    days: Optional[int] = None
) -> Dict[str, Any]:
    """Prunes execution and audit logs older than retention period."""
    start_time = datetime.now(timezone.utc)
    retention_days = days or getattr(settings, "data_retention_days", 90)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

    async with async_session_scope() as session:
        # Delete old AgentRuns
        del_runs = await session.execute(
            delete(AgentRun).where(AgentRun.created_at < cutoff_date)
        )
        runs_deleted = del_runs.rowcount

        # Delete old WorkflowExecutions
        del_wf = await session.execute(
            delete(WorkflowExecution).where(WorkflowExecution.started_at < cutoff_date)
        )
        wf_deleted = del_wf.rowcount

        await session.commit()

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(f"Retention cleanup purged {runs_deleted} agent runs and {wf_deleted} workflow executions older than {retention_days} days.")
    return {
        "status": "completed",
        "retention_days": retention_days,
        "agent_runs_deleted": runs_deleted,
        "workflow_executions_deleted": wf_deleted,
        "duration_seconds": duration
    }


@shared_task(bind=True, name="cleanup.cleanup_temp_files")
def cleanup_temp_files_task(
    self,
    temp_dir: Optional[str] = None,
    older_than_days: int = 7
) -> Dict[str, Any]:
    """Cleans up temporary files in upload/cache directories."""
    start_time = datetime.now(timezone.utc)
    target_dir = Path(temp_dir or getattr(settings, "upload_dir", "./temp_uploads"))

    if not target_dir.exists():
        return {
            "status": "completed",
            "message": f"Directory {target_dir} does not exist",
            "files_deleted": 0
        }

    cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).timestamp()
    files_deleted = 0
    bytes_freed = 0

    for file_path in target_dir.rglob("*"):
        if file_path.is_file():
            try:
                if file_path.stat().st_mtime < cutoff_ts:
                    size = file_path.stat().st_size
                    file_path.unlink()
                    files_deleted += 1
                    bytes_freed += size
            except Exception as e:
                logger.warning(f"Failed to delete {file_path}: {e}")

    return {
        "status": "completed",
        "directory": str(target_dir),
        "files_deleted": files_deleted,
        "bytes_freed": bytes_freed,
        "duration_seconds": (datetime.now(timezone.utc) - start_time).total_seconds()
    }


@shared_task(bind=True, name="cleanup.compress_logs")
def compress_logs_task(
    self,
    log_dir: Optional[str] = None,
    older_than_days: int = 7
) -> Dict[str, Any]:
    """Compresses rotated .log files into .gz archives."""
    start_time = datetime.now(timezone.utc)
    target_dir = Path(log_dir or "./logs")

    if not target_dir.exists():
        return {"status": "completed", "files_compressed": 0}

    cutoff_ts = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).timestamp()
    compressed_count = 0

    for log_file in target_dir.glob("*.log"):
        if log_file.is_file() and log_file.stat().st_mtime < cutoff_ts:
            gz_path = log_file.with_suffix(".log.gz")
            try:
                with open(log_file, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                    f_out.writelines(f_in)
                log_file.unlink()
                compressed_count += 1
            except Exception as e:
                logger.warning(f"Failed to compress {log_file}: {e}")

    return {
        "status": "completed",
        "files_compressed": compressed_count,
        "duration_seconds": (datetime.now(timezone.utc) - start_time).total_seconds()
    }