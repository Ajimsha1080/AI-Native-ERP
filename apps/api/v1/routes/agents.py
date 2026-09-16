"""Agent routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from packages.database import get_db
from packages.database.models import Agent, AgentTool, ActionExecutionLog, User
from ..schemas.agent import (
    AgentCreate, AgentUpdate, AgentResponse,
    AgentCreateResponse, AgentExecutionCreate, AgentExecutionResponse,
    ToolCreate, ToolResponse
)
from ..schemas.base import PaginatedResponse
from packages.security.auth import get_current_user

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("", response_model=PaginatedResponse[AgentResponse])
async def list_agents(
    page: int = 1,
    page_size: int = 20,
    organization_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    business_unit_id: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[Any] = None
):
    """List agents.

    Args:
        page: Page number
        page_size: Items per page
        organization_id: Filter by organization
        workspace_id: Filter by workspace
        business_unit_id: Filter by business unit
        type: Filter by agent type
        status: Filter by status
        db: Database session
        current_user: Current authenticated user

    Returns:
        PaginatedResponse: Paginated list of agents
    """
    # Build query
    query = select(Agent)

    # Filter by organization
    if organization_id:
        query = query.where(Agent.organization_id == UUID(organization_id))

    # Filter by workspace
    if workspace_id:
        query = query.where(Agent.workspace_id == UUID(workspace_id))

    # Filter by business unit
    if business_unit_id:
        query = query.where(Agent.business_unit_id == UUID(business_unit_id))

    # Filter by type
    if type:
        query = query.where(Agent.type == type)

    # Filter by status
    if status:
        query = query.where(Agent.status == status)

    # Get total count
    count_query = select(func.count(Agent.id))
    if organization_id:
        count_query = count_query.where(Agent.organization_id == UUID(organization_id))
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

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await db.execute(query)
    agents = result.scalars().all()

    return {
        "items": agents,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get agent by ID.

    Args:
        agent_id: Agent ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        AgentResponse: Agent information

    Raises:
        HTTPException: If agent not found
    """
    result = await db.execute(
        select(Agent).where(Agent.id == UUID(agent_id))
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new agent.

    Args:
        agent_data: Agent creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        AgentCreateResponse: Created agent with ID

    Raises:
        HTTPException: If agent creation fails
    """
    # Check if agent with same name/slug already exists
    result = await db.execute(
        select(Agent).where(
            Agent.organization_id == agent_data.organization_id,
            Agent.slug == agent_data.slug
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent with this name/slug already exists"
        )

    # Create agent
    agent = Agent(
        name=agent_data.name,
        slug=agent_data.slug,
        description=agent_data.description,
        display_name=agent_data.display_name,
        icon=agent_data.icon,
        type=agent_data.type,
        organization_id=agent_data.organization_id,
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update agent.

    Args:
        agent_id: Agent ID
        agent_data: Agent update data
        db: Database session
        current_user: Current authenticated user

    Returns:
        AgentResponse: Updated agent

    Raises:
        HTTPException: If agent not found or update fails
    """
    result = await db.execute(
        select(Agent).where(Agent.id == UUID(agent_id))
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    # Update fields
    update_data = agent_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)

    # Update timestamp
    agent.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(agent)

    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete agent.

    Args:
        agent_id: Agent ID
        db: Database session
        current_user: Current authenticated user

    Raises:
        HTTPException: If agent not found or deletion fails
    """
    result = await db.execute(
        select(Agent).where(Agent.id == UUID(agent_id))
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute agent.

    Args:
        agent_id: Agent ID
        execution_data: Execution data
        db: Database session
        current_user: Current authenticated user

    Returns:
        AgentExecutionResponse: Execution response

    Raises:
        HTTPException: If agent not found or execution fails
    """
    # Get agent
    result = await db.execute(
        select(Agent).where(Agent.id == UUID(agent_id))
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    # Create execution
    execution = ActionExecutionLog(
        agent_id=UUID(agent_id),
        user_id=current_user.id,
        status="running",
        prompt=execution_data.prompt,
        parameters=execution_data.parameters,
        context=execution_data.context,
        started_at=datetime.utcnow()
    )

    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # Instantiate real agent and tool layer
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

    execution.completed_at = datetime.utcnow()
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List agent executions.

    Args:
        agent_id: Agent ID
        page: Page number
        page_size: Items per page
        status: Filter by status
        db: Database session
        current_user: Current authenticated user

    Returns:
        PaginatedResponse: Paginated list of executions
    """
    # Build query
    query = select(ActionExecutionLog).where(
        ActionExecutionLog.agent_id == UUID(agent_id)
    )

    # Filter by status
    if status:
        query = query.where(ActionExecutionLog.status == status)

    # Get total count
    count_query = select(func.count(ActionExecutionLog.id)).where(
        ActionExecutionLog.agent_id == UUID(agent_id)
    )
    if status:
        count_query = count_query.where(ActionExecutionLog.status == status)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute
    result = await db.execute(query)
    executions = result.scalars().all()

    return {
        "items": executions,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


@router.get("/types", response_model=List[str])
async def list_agent_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all agent types.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List[str]: List of agent types
    """
    # Get all unique types
    result = await db.execute(select(Agent.type).distinct())
    types = result.scalars().all()

    return list(types)
