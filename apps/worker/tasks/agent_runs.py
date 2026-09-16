"""
Celery asynchronous task for long-running LangGraph agent executions.
"""

import asyncio
from uuid import UUID
from typing import Dict, Any, Optional

from celery import shared_task

from packages.agents.graph.graph import run_erp_agent


@shared_task(bind=True, name="tasks.run_agent_async")
def run_agent_async(
    self,
    organization_id: str,
    user_id: str,
    user_role: str,
    prompt: str,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs the LangGraph orchestrator asynchronously."""
    return asyncio.run(
        run_erp_agent(
            organization_id=UUID(organization_id),
            user_id=UUID(user_id),
            user_role=user_role,
            prompt=prompt,
            session_id=session_id,
        )
    )
