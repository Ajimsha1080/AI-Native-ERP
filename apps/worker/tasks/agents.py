"""
Agent tasks.

Background tasks for AI agent operations, LangGraph execution, vector store indexing,
and performance tuning.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
import logging
import asyncio

from celery import shared_task
from sqlalchemy import select, update, and_, func

from packages.database.core import async_session_scope
from packages.database.models import Agent, User
from packages.database.models.erp.agent_runs import AgentRun, ToolExecution
from packages.agents.base import BaseAgent
from packages.agents.graph.graph import run_erp_agent
from packages.rag.vector_store import vector_store
from packages.config import get_settings

logger = logging.getLogger("worker.agents")
settings = get_settings()


@shared_task(bind=True, name="agent.execute_agent")
async def execute_agent_task(
    self,
    agent_id: str,
    user_id: str,
    input_data: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute an agent asynchronously using real LangGraph or BaseAgent ReAct engine."""
    start_time = datetime.now(timezone.utc)
    prompt = input_data.get("prompt") or input_data.get("task") or "Analyze ERP business status"

    async with async_session_scope() as session:
        # Verify Agent
        agent_res = await session.execute(select(Agent).where(Agent.id == UUID(agent_id)))
        agent = agent_res.scalar_one_or_none()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Verify User
        user_res = await session.execute(select(User).where(User.id == UUID(user_id)))
        user = user_res.scalar_one_or_none()
        if not user:
            raise ValueError(f"User {user_id} not found")

        org_id = agent.organization_id or user.organization_id or UUID("00000000-0000-0000-0000-000000000001")
        user_role = getattr(user, "role", "admin")
        if hasattr(user_role, "value"):
            user_role = user_role.value

        # Execute through LangGraph Multi-Agent Orchestrator
        try:
            agent_result = await run_erp_agent(
                organization_id=org_id,
                user_id=user.id,
                user_role=str(user_role),
                prompt=prompt,
                session_id=input_data.get("session_id", f"worker-sess-{uuid4().hex[:6]}")
            )

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            return {
                "status": "completed",
                "agent_id": agent_id,
                "user_id": user_id,
                "result": agent_result["response"],
                "tokens_used": agent_result.get("tokens_used", 100),
                "cost_usd": agent_result.get("cost_usd", 0.0002),
                "latency_ms": agent_result.get("latency_ms", int(execution_time * 1000)),
                "routed_to": agent_result.get("routed_to", agent.name)
            }
        except Exception as e:
            logger.error(f"LangGraph execution fallback to BaseAgent: {e}")
            # Fallback to direct BaseAgent ReAct loop
            base_agent = BaseAgent(name=agent.name, role=agent.role or "Autonomous Specialist")
            fallback_res = await base_agent.execute_task(prompt)

            execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            return {
                "status": "completed",
                "agent_id": agent_id,
                "user_id": user_id,
                "result": fallback_res.get("output", "Task completed."),
                "tool_calls": fallback_res.get("tool_calls", []),
                "execution_time": execution_time
            }


@shared_task(bind=True, name="agent.train_agent")
async def train_agent_task(
    self,
    agent_id: str,
    training_data: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Train or fine-tune an agent with domain context."""
    start_time = datetime.now(timezone.utc)

    async with async_session_scope() as session:
        agent_res = await session.execute(select(Agent).where(Agent.id == UUID(agent_id)))
        agent = agent_res.scalar_one_or_none()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        # Ingest instructions or examples into agent config
        examples = training_data.get("examples", [])
        system_prompt = training_data.get("system_prompt")

        agent_config = dict(agent.config or {})
        if system_prompt:
            agent_config["system_prompt"] = system_prompt
        if examples:
            agent_config["few_shot_examples"] = examples
        
        agent.config = agent_config
        agent.updated_at = datetime.now(timezone.utc)
        await session.commit()

    return {
        "status": "completed",
        "agent_id": agent_id,
        "updated_config_keys": list(agent_config.keys()),
        "training_time": (datetime.now(timezone.utc) - start_time).total_seconds()
    }


@shared_task(bind=True, name="agent.update_agent_knowledge")
async def update_agent_knowledge_task(
    self,
    agent_id: str,
    knowledge_updates: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Update agent knowledge vector store with enterprise documents."""
    start_time = datetime.now(timezone.utc)
    docs_to_index = []
    ids = []
    metadatas = []

    for item in knowledge_updates:
        content = item.get("content") or item.get("text") or ""
        if content:
            doc_id = item.get("id") or f"doc-{uuid4()}"
            docs_to_index.append(content)
            ids.append(doc_id)
            metadatas.append({
                "agent_id": str(agent_id),
                "source": item.get("source", "worker_ingestion"),
                "department": item.get("department", "all"),
                "indexed_at": datetime.now(timezone.utc).isoformat()
            })

    if docs_to_index:
        vector_store.add_documents(
            collection_name="agentic_knowledge",
            documents=docs_to_index,
            metadatas=metadatas,
            ids=ids
        )

    return {
        "status": "completed",
        "agent_id": agent_id,
        "documents_indexed": len(docs_to_index),
        "update_time": (datetime.now(timezone.utc) - start_time).total_seconds()
    }


@shared_task(bind=True, name="agent.optimize_agent_performance")
async def optimize_agent_performance_task(
    self,
    agent_id: str,
    performance_metrics: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Optimize agent inference parameters based on latency/accuracy feedback."""
    start_time = datetime.now(timezone.utc)

    async with async_session_scope() as session:
        agent_res = await session.execute(select(Agent).where(Agent.id == UUID(agent_id)))
        agent = agent_res.scalar_one_or_none()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        agent_config = dict(agent.config or {})
        # Optimize temperature & max_tokens based on metrics
        if performance_metrics.get("high_latency"):
            agent_config["max_tokens"] = min(agent_config.get("max_tokens", 2000), 1000)
        if performance_metrics.get("hallucination_detected"):
            agent_config["temperature"] = 0.1

        agent.config = agent_config
        agent.updated_at = datetime.now(timezone.utc)
        await session.commit()

    return {
        "status": "completed",
        "agent_id": agent_id,
        "new_settings": agent_config,
        "optimization_time": (datetime.now(timezone.utc) - start_time).total_seconds()
    }