"""
Workflows API routes.

Manage AI agent workflows and their executions.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func
from datetime import datetime

from packages.database import get_db
from packages.database.models import Workflow, WorkflowExecution, User, Agent
from packages.security import get_current_active_user, check_endpoint_rate_limit
from packages.schemas.workflows import (
    WorkflowCreate, WorkflowUpdate, WorkflowResponse, WorkflowExecutionRequest,
    WorkflowExecutionResponse, WorkflowExecutionStatus, WorkflowExecutionLog
)

router = APIRouter(prefix="/workflows", tags=["workflows"])

# Rate limiting
rate_limiter = check_endpoint_rate_limit


@router.get("/", response_model=List[WorkflowResponse])
async def list_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    category: Optional[str] = Query(None, description="Filter by category"),
    agent_id: Optional[UUID] = Query(None, description="Filter by agent ID"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    rate_limiter: bool = Depends(rate_limiter)
):
    """List available workflows."""
    query = select(Workflow)
    
    # Apply filters
    if category:
        query = query.where(Workflow.category == category)
    
    if agent_id:
        query = query.where(Workflow.agent_id == agent_id)
    
    if search:
        search_condition = or_(
            Workflow.name.ilike(f"%{search}%"),
            Workflow.description.ilike(f"%{search}%")
        )
        query = query.where(search_condition)
    
    if status:
        query = query.where(Workflow.status == status)
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    workflows = result.scalars().all()
    
    return workflows


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID = Path(..., description="Workflow ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get workflow details."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    return workflow


@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new workflow."""
    # Check if workflow name already exists
    result = await db.execute(select(Workflow).where(Workflow.name == workflow.name))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow with this name already exists"
        )
    
    # Check if agent exists
    agent_result = await db.execute(select(Agent).where(Agent.id == workflow.agent_id))
    agent = agent_result.scalar_one_or_none()
    
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # Create workflow
    db_workflow = Workflow(**workflow.model_dump())
    db.add(db_workflow)
    await db.commit()
    await db.refresh(db_workflow)
    
    return db_workflow


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    workflow_update: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update workflow."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    db_workflow = result.scalar_one_or_none()
    
    if db_workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Update workflow fields
    for field, value in workflow_update.model_dump(exclude_unset=True).items():
        setattr(db_workflow, field, value)
    
    await db.commit()
    await db.refresh(db_workflow)
    
    return db_workflow


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete workflow."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    db_workflow = result.scalar_one_or_none()
    
    if db_workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Check if workflow has running executions
    execution_result = await db.execute(
        select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow_id)
    )
    if execution_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete workflow that has running executions"
        )
    
    await db.delete(db_workflow)
    await db.commit()


@router.post("/{workflow_id}/execute", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: UUID,
    request: WorkflowExecutionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Execute a workflow."""
    # Get workflow details
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Check if workflow is active
    if workflow.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow is not active"
        )
    
    # Create workflow execution record
    from packages.models import WorkflowExecution
    execution = WorkflowExecution(
        workflow_id=workflow_id,
        user_id=current_user.id,
        input_data=request.input_data or {},
        status=WorkflowExecutionStatus.PENDING
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    
    # TODO: Implement workflow execution
    # This should:
    # 1. Queue the workflow for execution
    # 2. Process the workflow steps
    # 3. Update execution status
    # 4. Return execution results
    # 5. Handle errors and timeouts
    
    # For now, simulate execution
    execution.status = WorkflowExecutionStatus.RUNNING
    execution.started_at = datetime.utcnow()
    await db.commit()
    
    # Simulate execution completion
    import asyncio
    await asyncio.sleep(2)  # Simulate processing time
    
    execution.status = WorkflowExecutionStatus.COMPLETED
    execution.completed_at = datetime.utcnow()
    execution.output_data = {"result": "Mock workflow execution completed", "steps": 5}
    execution.execution_time = 2.0
    await db.commit()
    
    return execution


@router.get("/{workflow_id}/executions", response_model=List[WorkflowExecutionResponse])
async def get_workflow_executions(
    workflow_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[WorkflowExecutionStatus] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get workflow executions."""
    # Check if workflow exists
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Get executions for this workflow
    query = select(WorkflowExecution).where(WorkflowExecution.workflow_id == workflow_id)
    
    if status:
        query = query.where(WorkflowExecution.status == status)
    
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    executions = result.scalars().all()
    
    return executions


@router.get("/{workflow_id}/executions/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_workflow_execution(
    workflow_id: UUID,
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get workflow execution details."""
    # Check if workflow exists
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Get execution
    result = await db.execute(
        select(WorkflowExecution)
        .where(and_(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.workflow_id == workflow_id
        ))
    )
    execution = result.scalar_one_or_none()
    
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    return execution


@router.get("/{workflow_id}/executions/{execution_id}/logs", response_model=List[WorkflowExecutionLog])
async def get_workflow_execution_logs(
    workflow_id: UUID,
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get workflow execution logs."""
    # Check if workflow exists
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found"
        )
    
    # Get execution
    result = await db.execute(
        select(WorkflowExecution)
        .where(and_(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.workflow_id == workflow_id
        ))
    )
    execution = result.scalar_one_or_none()
    
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    # TODO: Implement execution logging
    # This should return logs for the workflow execution
    
    # For now, return mock logs
    return [
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "level": "INFO",
            "message": "Workflow execution started",
            "step": "start"
        },
        {
            "timestamp": "2024-01-01T00:00:01Z",
            "level": "INFO",
            "message": "Step 1: Processing input data",
            "step": "step1"
        },
        {
            "timestamp": "2024-01-01T00:00:02Z",
            "level": "INFO",
            "message": "Step 1: Completed successfully",
            "step": "step1"
        }
    ]


@router.get("/categories", response_model=List[str])
async def get_workflow_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all workflow categories."""
    result = await db.execute(select(Workflow.category).distinct().where(Workflow.category.isnot(None)))
    categories = [row[0] for row in result.fetchall()]
    
    return categories


@router.get("/stats", response_model=Dict[str, Any])
async def get_workflow_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get workflow statistics."""
    # Count workflows by category
    category_counts = await db.execute(
        select(Workflow.category, func.count(Workflow.id))
        .group_by(Workflow.category)
    )
    category_stats = {row[0]: row[1] for row in category_counts.fetchall()}
    
    # Count total workflows
    total_workflows = await db.execute(select(func.count(Workflow.id)))
    total_count = total_workflows.scalar()
    
    # Get workflow execution stats
    execution_stats = await db.execute(
        select(
            WorkflowExecution.status,
            func.count(WorkflowExecution.id)
        )
        .group_by(WorkflowExecution.status)
    )
    status_stats = {row[0]: row[1] for row in execution_stats.fetchall()}
    
    # Get average execution time
    avg_time_result = await db.execute(
        select(func.avg(WorkflowExecution.execution_time))
        .where(WorkflowExecution.execution_time.isnot(None))
    )
    avg_time = avg_time_result.scalar()
    
    return {
        "total_workflows": total_count,
        "active_workflows": sum(1 for w in category_stats.values() if w > 0),
        "total_executions": sum(status_stats.values()),
        "category_distribution": category_stats,
        "execution_status_distribution": status_stats,
        "average_execution_time": avg_time or 0
    }


@router.get("/executions/{execution_id}/stop", response_model=WorkflowExecutionResponse)
async def stop_workflow_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Stop a running workflow execution."""
    # Get execution
    result = await db.execute(select(WorkflowExecution).where(WorkflowExecution.id == execution_id))
    execution = result.scalar_one_or_none()
    
    if execution is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    # Check if execution is running
    if execution.status not in [WorkflowExecutionStatus.PENDING, WorkflowExecutionStatus.RUNNING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Execution is not running"
        )
    
    # Update execution status
    execution.status = WorkflowExecutionStatus.STOPPED
    execution.completed_at = datetime.utcnow()
    execution.output_data = {"error": "Execution stopped by user"}
    
    await db.commit()
    await db.refresh(execution)
    
    return execution