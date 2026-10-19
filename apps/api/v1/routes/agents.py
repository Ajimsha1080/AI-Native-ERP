"""Agent routes with RBAC and tenant isolation."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from packages.database.models import Agent, AgentTool, ActionExecutionLog, User
from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_min_role
from ..schemas.agent import (
    AgentCreate, AgentUpdate, AgentResponse,
    AgentCreateResponse, AgentExecutionCreate, AgentExecutionResponse,
    ToolCreate, ToolResponse
)
from ..schemas.base import PaginatedResponse

router = APIRouter(prefix="/agents", tags=["Agents"])


def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("", response_model=PaginatedResponse[AgentResponse])
async def list_agents(
    page: int = 1,
    page_size: int = 20,
    workspace_id: Optional[str] = None,
    business_unit_id: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """List agents for current tenant organization."""
    query = select(Agent).where(Agent.organization_id == current_user.organization_id)

    if workspace_id:
        query = query.where(Agent.workspace_id == UUID(workspace_id))
    if business_unit_id:
        query = query.where(Agent.business_unit_id == UUID(business_unit_id))
    if type:
        query = query.where(Agent.type == type)
    if status:
        query = query.where(Agent.status == status)

    count_query = select(func.count(Agent.id)).where(Agent.organization_id == current_user.organization_id)
    if workspace_id:
        count_query = count_query.where(Agent.workspace_id == UUID(workspace_id))
    if business_unit_id:
        count_query = count_query.where(Agent.business_unit_id == UUID(business_unit_id))
    if type:
        count_query = count_query.where(Agent.type == type)
    if status:
        count_query = count_query.where(Agent.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    agents = result.scalars().all()

    return {
        "items": agents,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 1
    }


@router.get("/types", response_model=List[str])
async def list_agent_types(
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """List all agent types for current organization."""
    result = await db.execute(
        select(Agent.type).where(Agent.organization_id == current_user.organization_id).distinct()
    )
    types = result.scalars().all()
    return list(types)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """Get agent by ID within current tenant organization."""
    try:
        agent_uuid = UUID(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent UUID")

    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_uuid,
            Agent.organization_id == current_user.organization_id
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    return agent


@router.post("", response_model=AgentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    agent_data: AgentCreate,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(require_min_role("manager"))
):
    """Create a new agent (manager or above)."""
    # Enforce organization_id from current tenant
    org_id = current_user.organization_id

    result = await db.execute(
        select(Agent).where(
            Agent.organization_id == org_id,
            Agent.slug == agent_data.slug
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent with this name/slug already exists"
        )

    agent = Agent(
        name=agent_data.name,
        slug=agent_data.slug,
        description=agent_data.description,
        display_name=agent_data.display_name,
        icon=agent_data.icon,
        type=agent_data.type,
        organization_id=org_id,
        workspace_id=agent_data.workspace_id,
        business_unit_id=agent_data.business_unit_id,
        model_provider=agent_data.model_provider,
        model_name=agent_data.model_name,
        model_temperature=agent_data.model_temperature,
        model_max_tokens=agent_data.model_max_tokens,
        system_prompt=agent_data.system_prompt,
        requires_approval=agent_data.requires_approval,
        approval_threshold=agent_data.approval_threshold,
        status="draft",
        created_by_id=current_user.id
    )

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    return {
        "id": agent.id,
        "agent": agent
    }


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    agent_data: AgentUpdate,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(require_min_role("manager"))
):
    """Update agent (manager or above)."""
    try:
        agent_uuid = UUID(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent UUID")

    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_uuid,
            Agent.organization_id == current_user.organization_id
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    update_data = agent_data.model_dump(exclude_unset=True)
    # Disallow tampering with organization_id
    update_data.pop("organization_id", None)

    for field, value in update_data.items():
        setattr(agent, field, value)

    agent.updated_at = _utc_now()

    await db.commit()
    await db.refresh(agent)

    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(require_min_role("manager"))
):
    """Delete agent (manager or above)."""
    try:
        agent_uuid = UUID(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent UUID")

    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_uuid,
            Agent.organization_id == current_user.organization_id
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    await db.delete(agent)
    await db.commit()

    return None


@router.post("/{agent_id}/execute", response_model=AgentExecutionResponse)
async def execute_agent(
    agent_id: str,
    execution_data: AgentExecutionCreate,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(require_min_role("manager"))
):
    """Execute agent (manager or above)."""
    try:
        agent_uuid = UUID(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent UUID")

    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_uuid,
            Agent.organization_id == current_user.organization_id
        )
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    execution = ActionExecutionLog(
        organization_id=current_user.organization_id,
        agent_id=agent_uuid,
        user_id=current_user.id,
        status="running",
        prompt=execution_data.prompt,
        parameters=execution_data.parameters,
        context=execution_data.context,
        started_at=_utc_now()
    )

    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    from packages.agents.base import BaseAgent
    from packages.tools.erp_tools import AgentToolLayer

    agent_runner = BaseAgent(
        name=agent.name,
        role=agent.description or agent.name,
        system_prompt=agent.system_prompt,
        model_name=agent.model_name,
        temperature=agent.model_temperature or 0.0
    )
    tool_layer = AgentToolLayer(agent_id=str(agent.id), db_session=db)

    try:
        res = await agent_runner.execute_task(
            prompt=execution_data.prompt,
            context=execution_data.context,
            tool_layer=tool_layer
        )
        execution.status = "completed"
        execution.output = res.get("output", "Task completed.")
        execution.output_tokens = res.get("tokens_used", 150)
        execution.execution_steps = res.get("tool_calls", [])
    except Exception as e:
        execution.status = "failed"
        execution.error_message = str(e)
        execution.output = f"Execution failed: {e}"

    execution.completed_at = _utc_now()
    execution.duration_seconds = max(1, int((execution.completed_at - execution.started_at).total_seconds()))

    await db.commit()
    await db.refresh(execution)

    return execution


@router.get("/{agent_id}/executions", response_model=PaginatedResponse[AgentExecutionResponse])
async def list_agent_executions(
    agent_id: str,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """List agent executions."""
    try:
        agent_uuid = UUID(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid agent UUID")

    # Verify agent belongs to current tenant
    agent_res = await db.execute(
        select(Agent.id).where(Agent.id == agent_uuid, Agent.organization_id == current_user.organization_id)
    )
    if not agent_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Agent not found")

    query = select(ActionExecutionLog).where(
        ActionExecutionLog.agent_id == agent_uuid,
        ActionExecutionLog.organization_id == current_user.organization_id
    )

    if status:
        query = query.where(ActionExecutionLog.status == status)

    count_query = select(func.count(ActionExecutionLog.id)).where(
        ActionExecutionLog.agent_id == agent_uuid,
        ActionExecutionLog.organization_id == current_user.organization_id
    )
    if status:
        count_query = count_query.where(ActionExecutionLog.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    executions = result.scalars().all()

    return {
        "items": executions,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 1
    }


@router.get("/observability/status")
async def get_agent_observability_status(
    current_user: CurrentUser,
):
    """Returns LangSmith agent tracing status and observability metrics."""
    from packages.observability.langsmith_client import langsmith_manager
    return langsmith_manager.test_connection()

