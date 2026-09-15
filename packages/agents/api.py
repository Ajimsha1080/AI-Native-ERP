from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel, ConfigDict

from packages.agents import models
from packages.agents.database import get_db

router = APIRouter(prefix="/agents", tags=["Agents"])

class AgentCreate(BaseModel):
    name: str
    role: str

class AgentResponse(BaseModel):
    id: int
    name: str
    role: str
    status: str
    successRate: str | None = "100%"
    actions: int | None = 0

    model_config = ConfigDict(from_attributes=True)

DEFAULT_AGENTS = [
    {"name": "Finance Agent", "role": "Finance", "status": "Active", "success_rate": "100%", "actions": 0},
    {"name": "Inventory Agent", "role": "Inventory", "status": "Active", "success_rate": "100%", "actions": 0},
    {"name": "Procurement Agent", "role": "Procurement", "status": "Active", "success_rate": "100%", "actions": 0},
    {"name": "Sales Agent", "role": "Sales", "status": "Active", "success_rate": "100%", "actions": 0},
    {"name": "Operations Agent", "role": "Operations", "status": "Active", "success_rate": "100%", "actions": 0},
    {"name": "HR Agent", "role": "HR", "status": "Active", "success_rate": "100%", "actions": 0},
    {"name": "Analytics Agent", "role": "Analytics", "status": "Active", "success_rate": "100%", "actions": 0},
    {"name": "Compliance Agent", "role": "Compliance", "status": "Active", "success_rate": "100%", "actions": 0}
]

@router.post("/", response_model=AgentResponse)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    db_agent = models.AgentModel(
        name=agent.name,
        role=agent.role,
        status="Active",
        success_rate="100%",
        actions=0
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    
    return {
        "id": db_agent.id,
        "name": db_agent.name,
        "role": db_agent.role,
        "status": db_agent.status,
        "successRate": db_agent.success_rate,
        "actions": db_agent.actions
    }

@router.get("/", response_model=List[AgentResponse])
def get_agents(db: Session = Depends(get_db)):
    agents = db.query(models.AgentModel).all()
    if not agents:
        # Seed default agents
        for da in DEFAULT_AGENTS:
            db_agent = models.AgentModel(
                name=da["name"],
                role=da["role"],
                status=da["status"],
                success_rate=da["success_rate"],
                actions=da["actions"]
            )
            db.add(db_agent)
        db.commit()
        agents = db.query(models.AgentModel).all()

    return [
        {
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "status": a.status,
            "successRate": a.success_rate,
            "actions": a.actions
        } for a in agents
    ]

@router.delete("/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(models.AgentModel).filter(models.AgentModel.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()
    return {"ok": True}

@router.put("/{agent_id}/toggle")
def toggle_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(models.AgentModel).filter(models.AgentModel.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    agent.status = "Paused" if agent.status in ["Active", "idle", "running"] else "Active"
    db.commit()
    db.refresh(agent)
    
    return {
        "id": agent.id,
        "name": agent.name,
        "role": agent.role,
        "status": agent.status,
        "successRate": agent.success_rate,
        "actions": agent.actions
    }
