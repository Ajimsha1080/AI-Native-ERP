"""
Tools API routes with tenant isolation and RBAC.

Manage AI agent tools and their configurations.
"""

import time
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, func

from packages.database.models import Tool, User, Agent, AgentTool
from packages.database.tenant_context import TenantDB
from packages.auth.dependencies import CurrentUser, require_min_role
from packages.schemas.tools import (
    ToolCreate, ToolUpdate, ToolResponse, ToolResponseWithConfig,
    ToolExecutionRequest, ToolExecutionResponse, ToolType
)

router = APIRouter(prefix="/tools", tags=["tools"])


def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/", response_model=List[ToolResponse])
async def list_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    tool_type: Optional[ToolType] = Query(None, description="Filter by tool type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser),
):
    """List available tools for current tenant."""
    query = select(Tool).where(Tool.organization_id == current_user.organization_id)
    
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
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/categories", response_model=List[str])
async def get_tool_categories(
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """Get all tool categories."""
    result = await db.execute(
        select(Tool.category)
        .where(Tool.organization_id == current_user.organization_id, Tool.category.isnot(None))
        .distinct()
    )
    return [row[0] for row in result.fetchall()]


@router.get("/stats", response_model=Dict[str, Any])
async def get_tool_stats(
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """Get tool statistics for current tenant."""
    type_counts = await db.execute(
        select(Tool.type, func.count(Tool.id))
        .where(Tool.organization_id == current_user.organization_id)
        .group_by(Tool.type)
    )
    type_stats = {row[0]: row[1] for row in type_counts.fetchall()}
    
    category_counts = await db.execute(
        select(Tool.category, func.count(Tool.id))
        .where(Tool.organization_id == current_user.organization_id)
        .group_by(Tool.category)
    )
    category_stats = {row[0]: row[1] for row in category_counts.fetchall()}
    
    total_result = await db.execute(
        select(func.count(Tool.id)).where(Tool.organization_id == current_user.organization_id)
    )
    total_count = total_result.scalar() or 0
    
    return {
        "total_count": total_count,
        "type_distribution": type_stats,
        "category_distribution": category_stats
    }


@router.get("/available/{agent_id}", response_model=List[ToolResponse])
async def get_available_tools_for_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """Get tools available for a specific agent."""
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.organization_id == current_user.organization_id)
    )
    agent = result.scalar_one_or_none()
    
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    assigned = await db.execute(
        select(Tool)
        .join(AgentTool, AgentTool.tool_id == Tool.id)
        .where(
            AgentTool.agent_id == agent_id,
            AgentTool.enabled == True,
            Tool.organization_id == current_user.organization_id
        )
    )
    tools = assigned.scalars().all()
    if not tools:
        all_tools = await db.execute(
            select(Tool).where(Tool.organization_id == current_user.organization_id, Tool.is_enabled == True)
        )
        tools = all_tools.scalars().all()
    
    return tools


@router.get("/{tool_id}", response_model=ToolResponseWithConfig)
async def get_tool(
    tool_id: UUID = Path(..., description="Tool ID"),
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """Get tool details with configuration."""
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id, Tool.organization_id == current_user.organization_id)
    )
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
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(require_min_role("manager"))
):
    """Create a new tool (manager or above)."""
    result = await db.execute(
        select(Tool).where(Tool.name == tool.name, Tool.organization_id == current_user.organization_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tool with this name already exists"
        )
    
    tool_data = tool.model_dump()
    tool_data["organization_id"] = current_user.organization_id
    db_tool = Tool(**tool_data)
    db.add(db_tool)
    await db.commit()
    await db.refresh(db_tool)
    
    return db_tool


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: UUID,
    tool_update: ToolUpdate,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(require_min_role("manager"))
):
    """Update tool (manager or above)."""
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id, Tool.organization_id == current_user.organization_id)
    )
    db_tool = result.scalar_one_or_none()
    
    if db_tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    
    update_data = tool_update.model_dump(exclude_unset=True)
    update_data.pop("organization_id", None)
    for field, value in update_data.items():
        setattr(db_tool, field, value)
    
    await db.commit()
    await db.refresh(db_tool)
    
    return db_tool


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: UUID,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(require_min_role("manager"))
):
    """Delete tool (manager or above)."""
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id, Tool.organization_id == current_user.organization_id)
    )
    db_tool = result.scalar_one_or_none()
    
    if db_tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    
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


@router.post("/{tool_id}/enable", response_model=ToolResponse)
async def enable_tool(
    tool_id: UUID,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(require_min_role("manager"))
):
    """Enable a tool (manager or above)."""
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id, Tool.organization_id == current_user.organization_id)
    )
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
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(require_min_role("manager"))
):
    """Disable a tool (manager or above)."""
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id, Tool.organization_id == current_user.organization_id)
    )
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


@router.post("/{tool_id}/validate", response_model=Dict[str, Any])
async def validate_tool_inputs(
    tool_id: UUID,
    inputs: Dict[str, Any],
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(CurrentUser)
):
    """Validate tool inputs against schema."""
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id, Tool.organization_id == current_user.organization_id)
    )
    tool = result.scalar_one_or_none()
    
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    
    errors = []
    schema = tool.input_schema or {}
    if isinstance(schema, dict):
        required_fields = schema.get("required", [])
        for rf in required_fields:
            if rf not in inputs or inputs[rf] is None or inputs[rf] == "":
                errors.append(f"Missing required parameter: '{rf}'")

    return {
        "tool_id": str(tool_id),
        "tool_name": tool.name,
        "is_valid": len(errors) == 0,
        "errors": errors
    }


@router.post("/{tool_id}/execute", response_model=ToolExecutionResponse)
async def execute_tool(
    tool_id: UUID,
    request: ToolExecutionRequest,
    db: AsyncSession = Depends(TenantDB),
    current_user: User = Depends(require_min_role("manager"))
):
    """Execute a tool (manager or above)."""
    result = await db.execute(
        select(Tool).where(Tool.id == tool_id, Tool.organization_id == current_user.organization_id)
    )
    tool = result.scalar_one_or_none()
    
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found"
        )
    
    start_time = time.time()
    from packages.tools.erp_tools import AgentToolLayer
    tool_layer = AgentToolLayer(db_session=db)
    tool_slug = str(tool.slug or tool.name).lower()

    try:
        inputs = request.inputs or {}
        if "inventory" in tool_slug:
            output = await tool_layer.get_inventory(sku=inputs.get("sku"))
        elif "purchase" in tool_slug:
            output = await tool_layer.create_purchase_order(
                supplier_id=inputs.get("supplier_id", "SUP-DEFAULT"),
                items=inputs.get("items", []),
                amount=float(inputs.get("amount", 500.00))
            )
        elif "invoice" in tool_slug:
            output = await tool_layer.create_invoice(
                customer_id=inputs.get("customer_id", "CUST-DEFAULT"),
                amount=float(inputs.get("amount", 250.00))
            )
        elif "customer" in tool_slug:
            output = await tool_layer.get_customers()
        else:
            output = {"result": f"Executed tool {tool.name}", "inputs": inputs}

        execution_status = "success"
    except Exception as e:
        output = {"error": str(e)}
        execution_status = "error"

    duration = round(time.time() - start_time, 3)

    return {
        "tool_id": tool_id,
        "tool_name": tool.name,
        "status": execution_status,
        "output": output,
        "execution_time": duration,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    }