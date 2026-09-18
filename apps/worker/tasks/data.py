"""
Data tasks.

Background tasks for data processing, analytics aggregation, and system telemetry.
Uses real psutil system measurements and PostgreSQL database execution analytics.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import logging
import psutil

from celery import shared_task
from sqlalchemy import select, and_, func, case

from packages.database.core import async_session_scope
from packages.database.models import User, Workflow, WorkflowExecution, Agent
from packages.database.models.erp.agent_runs import AgentRun
from packages.config import get_settings

logger = logging.getLogger("worker.data")
settings = get_settings()


def get_real_system_metrics() -> Dict[str, Any]:
    """Measures real OS-level CPU, Memory, and Disk utilization."""
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(".")

        return {
            "cpu_usage_pct": round(cpu, 1),
            "cpu_usage": f"{round(cpu, 1)}%",
            "memory_usage_pct": round(mem.percent, 1),
            "memory_usage": f"{round(mem.percent, 1)}%",
            "memory_available_mb": round(mem.available / (1024 * 1024), 1),
            "disk_usage_pct": round(disk.percent, 1),
            "disk_usage": f"{round(disk.percent, 1)}%",
            "disk_free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
        }
    except Exception as e:
        logger.warning(f"Could not read psutil metrics: {e}")
        return {
            "cpu_usage": "N/A",
            "memory_usage": "N/A",
            "disk_usage": "N/A",
        }


@shared_task(bind=True, name="data.generate_system_metrics")
async def generate_system_metrics_task(
    self,
    days: int = 7,
    include_realtime: bool = True
) -> Dict[str, Any]:
    """Generates system metrics and operational analytics."""
    start_time = datetime.now(timezone.utc)
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    async with async_session_scope() as session:
        # Count active users
        user_res = await session.execute(
            select(func.count(User.id)).where(User.is_active == True)
        )
        active_users = user_res.scalar() or 0

        # Count active agents
        agent_res = await session.execute(
            select(func.count(Agent.id)).where(Agent.status == "active")
        )
        active_agents = agent_res.scalar() or 0

        # Count active workflows
        wf_res = await session.execute(
            select(func.count(Workflow.id))
        )
        total_workflows = wf_res.scalar() or 0

        # Count agent runs in period
        runs_res = await session.execute(
            select(
                func.count(AgentRun.id),
                func.coalesce(func.sum(AgentRun.token_input + AgentRun.token_output), 0),
                func.coalesce(func.sum(AgentRun.cost_usd), 0.0),
                func.coalesce(func.avg(AgentRun.latency_ms), 0.0)
            ).where(AgentRun.created_at >= cutoff_date)
        )
        run_count, total_tokens, total_cost, avg_latency = runs_res.first()

        # Count workflow executions in period
        wf_exec_res = await session.execute(
            select(
                func.count(WorkflowExecution.id),
                func.coalesce(func.avg(WorkflowExecution.duration_seconds), 0.0)
            ).where(WorkflowExecution.started_at >= cutoff_date)
        )
        wf_exec_count, avg_wf_time = wf_exec_res.first()

    metrics = {
        "status": "completed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "days_analyzed": days,
        "overview": {
            "active_users": active_users,
            "active_agents": active_agents,
            "total_workflows": total_workflows,
            "agent_runs_period": run_count,
            "total_tokens_consumed": int(total_tokens),
            "total_cost_usd": float(total_cost),
            "avg_agent_latency_ms": float(avg_latency),
            "workflow_executions_period": wf_exec_count,
            "avg_workflow_time_s": float(avg_wf_time),
        }
    }

    if include_realtime:
        metrics["system_telemetry"] = get_real_system_metrics()

    metrics["generation_time_s"] = (datetime.now(timezone.utc) - start_time).total_seconds()
    return metrics