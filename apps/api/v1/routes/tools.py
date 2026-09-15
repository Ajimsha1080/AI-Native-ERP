"""
Tools API routes.

Manage AI agent tools and their configurations.
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func

from packages.database import get_db
from packages.database.models import Tool, User
from packages.security.auth import get_current_user, get_current_active_user
from packages.security.rates import check_endpoint_rate_limit
from packages.schemas.tools import (
    ToolCreate, ToolUpdate, ToolResponse, ToolResponseWithConfig,
    ToolExecutionRequest, ToolExecutionResponse, ToolType
)

router = APIRouter(prefix="/tools", tags=["tools"])

# Rate limiting
rate_limiter = check_endpoint_rate_limit


@router.get("/", response_model=List[ToolResponse])
async def list_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    tool_type: Optional[ToolType] = Query(None, description="Filter by tool type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    rate_limiter: bool = Depends(rate_limiter)
):
    """List available tools."""
    query = select(Tool)
    
    # Apply filters
    if tool_type:
        query = query.where(Tool.type == tool_type)
    
    if category:
        query = query.where(Tool.category == category)
    
    if search:
        search_condition = or_(
            Tool.name.ilike(f"%{search}%"),
            Tool.description.ilike(f"%{search}%")
        )
        query = query.where(search_condition)
    
    # Apply pagination
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    tools = result.scalars().all()
    
    return tools


@router.get("/{tool_id}", response_model=ToolResponseWithConfig)
async def get_tool(
    tool_id: UUID = Path(..., description="Tool ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get tool details with configuration."""
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    
    return tool


@router.post("/", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    tool: ToolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create a new tool."""
    # Check if tool name already exists
    result = await db.execute(select(Tool).where(Tool.name == tool.name))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool with this name already exists"
        )
    
    # Create tool
    db_tool = Tool(**tool.model_dump())
    db.add(db_tool)
    await db.commit()
    await db.refresh(db_tool)
    
    return db_tool


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: UUID,
    tool_update: ToolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update tool."""
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    db_tool = result.scalar_one_or_none()
    
    if db_tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    
    # Update tool fields
    for field, value in tool_update.model_dump(exclude_unset=True).items():
        setattr(db_tool, field, value)
    
    await db.commit()
    await db.refresh(db_tool)
    
    return db_tool


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete tool."""
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    db_tool = result.scalar_one_or_none()
    
    if db_tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    
    # Check if tool is being used by any agents
    from packages.database.models import AgentTool
    agent_tool_result = await db.execute(
        select(AgentTool).where(AgentTool.tool_id == tool_id)
    )
    if agent_tool_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete tool that is being used by agents"
        )
    
    await db.delete(db_tool)
    await db.commit()


@router.post("/{tool_id}/execute", response_model=ToolExecutionResponse)
async def execute_tool(
    tool_id: UUID,
    request: ToolExecutionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Execute a tool."""
    # Get tool details
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    
    # TODO: Implement tool execution
    # This should:
    # 1. Validate input against schema
    # 2. Execute the tool with the provided inputs
    # 3. Return the results
    # 4. Handle errors and timeouts
    
    # For now, return mock response
    return {
        "tool_id": tool_id,
        "tool_name": tool.name,
        "status": "success",
        "output": "Mock execution result",
        "execution_time": 0.5,
        "timestamp": "2024-01-01T00:00:00Z"
    }


@router.get("/categories", response_model=List[str])
async def get_tool_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all tool categories."""
    result = await db.execute(select(Tool.category).distinct().where(Tool.category.isnot(None)))
    categories = [row[0] for row in result.fetchall()]
    
    return categories


@router.get("/stats", response_model=Dict[str, Any])
async def get_tool_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get tool statistics."""
    # Count tools by type
    type_counts = await db.execute(
        select(Tool.type, func.count(Tool.id))
        .group_by(Tool.type)
    )
    type_stats = {row[0]: row[1] for row in type_counts.fetchall()}
    
    # Count tools by category
    category_counts = await db.execute(
        select(Tool.category, func.count(Tool.id))
        .group_by(Tool.category)
    )
    category_stats = {row[0]: row[1] for row in category_counts.fetchall()}
    
    # Get total tool count
    total_result = await db.execute(select(func.count(Tool.id)))
    total_count = total_result.scalar()
    
    return {
        "total_count": total_count,
        "type_distribution": type_stats,
        "category_distribution": category_stats
    }


@router.post("/{tool_id}/validate", response_model=Dict[str, Any])
async def validate_tool_inputs(
    tool_id: UUID,
    inputs: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Validate tool inputs against schema."""
    # Get tool details
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    
    # TODO: Implement input validation against tool config_schema
    # This should validate the inputs against the JSON schema
    
    return {
        "tool_id": tool_id,
        "is_valid": True,
        "errors": []
    }


@router.get("/available/{agent_id}", response_model=List[ToolResponse])
async def get_available_tools_for_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get tools available for a specific agent."""
    # Check if agent exists and user has access
    from packages.database.models import Agent
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    # TODO: Implement tool filtering based on agent capabilities and requirements
    # For now, return all available tools
    
    result = await db.execute(select(Tool))
    tools = result.scalars().all()
    
    return tools


@router.post("/{tool_id}/enable", response_model=ToolResponse)
async def enable_tool(
    tool_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Enable a tool."""
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    
    tool.is_enabled = True
    await db.commit()
    await db.refresh(tool)
    
    return tool


@router.post("/{tool_id}/disable", response_model=ToolResponse)
async def disable_tool(
    tool_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Disable a tool."""
    result = await db.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    
    tool.is_enabled = False
    await db.commit()
    await db.refresh(tool)
    
    return tool