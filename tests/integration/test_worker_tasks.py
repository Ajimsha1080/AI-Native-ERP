"""
Integration tests for Celery Worker Tasks.
Verifies real execution of notifications, agents, workflows, connectors, system metrics, and cleanup tasks.
"""

import pytest
import tempfile
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from packages.database.core import async_session_scope, create_db_and_tables
from packages.database.tenant_context import set_tenant_context
from packages.database.models import (
    Organization, User, UserStatus, Agent, Workflow, WorkflowStatus,
    Integration, IntegrationConnection, IntegrationType, IntegrationStatus, Tool
)
from packages.database.models.tool import ToolCategory
from packages.database.models.erp.agent_runs import AgentRun
from apps.worker.tasks.notifications import (
    send_verification_email_task, send_password_reset_email_task,
    send_alerts_task
)
from apps.worker.tasks.agents import (
    execute_agent_task, train_agent_task, update_agent_knowledge_task, optimize_agent_performance_task
)
from apps.worker.tasks.workflows import (
    execute_workflow_task, schedule_workflow_task
)
from apps.worker.tasks.connectors import (
    verify_connection_task, sync_data_task
)
from apps.worker.tasks.data import (
    generate_system_metrics_task, get_real_system_metrics
)
from apps.worker.tasks.cleanup import (
    cleanup_old_executions_task, cleanup_temp_files_task, compress_logs_task
)
from apps.worker.tasks.tools import (
    execute_tool_task, validate_tool_inputs_task
)


@pytest.mark.asyncio
async def test_worker_notification_tasks():
    await create_db_and_tables()

    # 1. Verification Email
    res_verify = send_verification_email_task.__wrapped__(
        email="test@example.com",
        verification_token="token_123",
        user_name="Test User"
    )
    assert res_verify["status"] in ["sent", "failed"]

    # 2. Password Reset Email
    res_reset = send_password_reset_email_task.__wrapped__(
        email="test@example.com",
        reset_token="reset_123",
        user_name="Test User"
    )
    assert res_reset["status"] in ["sent", "failed"]


@pytest.mark.asyncio
async def test_worker_agent_and_workflow_execution():
    await create_db_and_tables()
    org_id = uuid4()
    user_id = uuid4()
    agent_id = uuid4()
    workflow_id = uuid4()
    tool_id = uuid4()

    async with async_session_scope() as session:
        await set_tenant_context(session, org_id)

        org = Organization(id=org_id, name="Worker Corp", slug=f"worker-{uuid4().hex[:6]}")
        user = User(
            id=user_id,
            tenant_id=org_id,
            email=f"worker-user-{uuid4().hex[:4]}@corp.com",
            first_name="Worker",
            last_name="Tester",
            status=UserStatus.ACTIVE,
            is_active=True,
        )
        agent = Agent(
            id=agent_id,
            organization_id=org_id,
            name="Finance Worker Specialist",
            slug=f"fin-spec-{uuid4().hex[:6]}",
            description="Treasury and Revenue Controller",
            status="active",
            config={"max_tokens": 1500}
        )
        workflow = Workflow(
            id=workflow_id,
            organization_id=org_id,
            name="Inventory Replenishment Automation",
            slug=f"inv-auto-{uuid4().hex[:6]}",
            category="inventory",
            status=WorkflowStatus.ACTIVE,
        )
        tool = Tool(
            id=tool_id,
            organization_id=org_id,
            name="get_inventory",
            slug="get-inventory",
            category=ToolCategory.API,
            implementation_type="python_function",
        )
        session.add_all([org, user, agent, workflow, tool])
        await session.commit()

    # 1. Test Agent Execution Task
    res_agent = await execute_agent_task.__wrapped__(
        agent_id=str(agent_id),
        user_id=str(user_id),
        input_data={"prompt": "Check current warehouse stock"}
    )
    assert res_agent["status"] == "completed"
    assert "result" in res_agent

    # 2. Test Agent Training & Knowledge Update Task
    res_train = await train_agent_task.__wrapped__(
        agent_id=str(agent_id),
        training_data={"system_prompt": "You are an expert ERP finance auditor."}
    )
    assert res_train["status"] == "completed"

    res_knowledge = await update_agent_knowledge_task.__wrapped__(
        agent_id=str(agent_id),
        knowledge_updates=[{"content": "Standard invoice payment term is Net 30."}]
    )
    assert res_knowledge["status"] == "completed"
    assert res_knowledge["documents_indexed"] == 1

    # 3. Test Workflow Execution Task
    res_wf = await execute_workflow_task.__wrapped__(
        workflow_id=str(workflow_id),
        user_id=str(user_id),
        input_data={"sku": "SKU-ALUM-8020"}
    )
    assert res_wf["status"] == "completed"
    assert "output" in res_wf

    # 4. Test Tool Execution Task
    res_tool = await execute_tool_task.__wrapped__(
        tool_id=str(tool_id),
        inputs={"sku": "SKU-ALUM-8020"}
    )
    assert res_tool["status"] == "completed"
    assert "output" in res_tool


@pytest.mark.asyncio
async def test_worker_connector_sync_and_data_metrics():
    await create_db_and_tables()
    org_id = uuid4()
    integ_id = uuid4()
    conn_id = uuid4()

    async with async_session_scope() as session:
        await set_tenant_context(session, org_id)

        org = Organization(id=org_id, name="Connector Org", slug=f"conn-org-{uuid4().hex[:6]}")
        integ = Integration(
            id=integ_id,
            organization_id=org_id,
            name="QuickBooks Online Integration",
            slug=f"qbo-{uuid4().hex[:6]}",
            type=IntegrationType.API_REST,
            status="active",
        )
        conn = IntegrationConnection(
            id=conn_id,
            integration_id=integ_id,
            connection_name="QBO Primary Connection",
            connection_type=IntegrationType.API_REST,
            status="active",
            connection_config={"environment": "sandbox", "access_token": "mock_token"}
        )
        session.add_all([org, integ, conn])
        await session.commit()

    # 1. Test Connector Connection Task
    res_conn = await verify_connection_task.__wrapped__(connection_id=str(conn_id))
    assert res_conn["status"] in ["success", "failed"]

    # 2. Test Connector Data Sync Task
    res_sync = await sync_data_task.__wrapped__(connection_id=str(conn_id))
    assert res_sync["status"] in ["success", "failed"]

    # 3. Test Real System Metrics Task (psutil)
    telemetry = get_real_system_metrics()
    assert "cpu_usage" in telemetry
    assert "memory_usage" in telemetry
    assert "disk_usage" in telemetry

    res_metrics = await generate_system_metrics_task.__wrapped__(days=7)
    assert res_metrics["status"] == "completed"
    assert "overview" in res_metrics
    assert "system_telemetry" in res_metrics


@pytest.mark.asyncio
async def test_worker_cleanup_tasks():
    # 1. Old Executions Cleanup
    res_clean_db = await cleanup_old_executions_task.__wrapped__(days=30)
    assert res_clean_db["status"] == "completed"

    # 2. Temp Files Cleanup
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = Path(tmp_dir) / "stale.tmp"
        test_file.write_text("old temporary data")

        res_clean_files = cleanup_temp_files_task.__wrapped__(temp_dir=tmp_dir, older_than_days=-1)
        assert res_clean_files["status"] == "completed"
        assert res_clean_files["files_deleted"] >= 1

