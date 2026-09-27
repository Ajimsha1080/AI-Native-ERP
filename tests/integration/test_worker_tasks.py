import pytest
import os
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from tests.conftest import ASYNC_TEST_DB_URL
from packages.database.tenant_context import set_tenant_context
from packages.database.models import (
    Organization, User, Agent, Workflow, WorkflowExecution, Integration, IntegrationConnection, AuditEvent
)
from packages.database.models.erp.agent_runs import AgentRun
from apps.worker.tasks.notifications import (
    _dispatch_smtp_sync,
    send_verification_email_task,
    send_password_reset_email_task,
    send_alerts_task,
    send_workflow_notifications_task,
    send_agent_notifications_task,
)
from apps.worker.tasks.agents import (
    execute_agent_task,
    train_agent_task,
    update_agent_knowledge_task,
    optimize_agent_performance_task,
)
from apps.worker.tasks.workflows import (
    execute_workflow_task,
    schedule_workflow_task,
)
from apps.worker.tasks.connectors import (
    verify_connection_task,
    sync_data_task,
)
from apps.worker.tasks.data import (
    get_real_system_metrics,
    generate_system_metrics_task,
)
from apps.worker.tasks.cleanup import (
    cleanup_old_executions_task,
    cleanup_temp_files_task,
    compress_logs_task,
)


@pytest.mark.asyncio
async def test_notifications_tasks():
    """Verifies SMTP notifications dispatch and audit recording against PostgreSQL."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()

    async with session_factory() as session:
        org = Organization(
            id=org_id,
            name="Notify Test Org",
            slug=f"notify-{org_id.hex[:6]}",
            plan="enterprise",
            status="active"
        )
        user = User(
            id=user_id,
            tenant_id=org_id,
            email=f"tester-{uuid4().hex[:4]}@example.com",
            first_name="Tester",
            last_name="Notifications",
            full_name="Tester Notifications",
            password_hash="hashed_pw",
            status="active",
            is_active=True,
        )
        session.add_all([org, user])
        await session.commit()

    with patch("apps.worker.tasks.notifications._dispatch_smtp_sync", return_value=True):
        # 1. Verification and Password Reset Emails
        verif_res = send_verification_email_task(
            email="user@example.com",
            verification_token="token_abc_123",
            user_name="John Doe"
        )
        assert verif_res["status"] == "sent"
        assert verif_res["recipient"] == "user@example.com"

        reset_res = send_password_reset_email_task(
            email="user@example.com",
            reset_token="reset_xyz_456",
            user_name="John Doe"
        )
        assert reset_res["status"] == "sent"
        assert reset_res["recipient"] == "user@example.com"

        # 2. Security Alerts Task
        alert_res = await send_alerts_task(
            alert_type="UNAUTHORIZED_ACCESS",
            recipient_ids=[str(user_id)],
            alert_data={"title": "Suspicious Login", "message": "Login from unknown IP"}
        )
        assert alert_res["status"] == "completed"
        assert alert_res["successful"] == 1
        assert alert_res["failed"] == 0

        # 3. Workflow Notifications Task
        wf_id = uuid4()
        exec_id = uuid4()
        async with session_factory() as session:
            wf = Workflow(
                id=wf_id,
                organization_id=org_id,
                name="Invoice Auto-Approval",
                slug=f"wf-{wf_id.hex[:6]}",
                category="finance",
                created_by_id=user_id,
            )
            wf_exec = WorkflowExecution(
                id=exec_id,
                workflow_id=wf_id,
                triggered_by_id=user_id,
                trigger_type="manual",
                status="completed",
                duration_seconds=5,
                started_at=datetime.now(timezone.utc).replace(tzinfo=None),
                completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add_all([wf, wf_exec])
            await session.commit()

        wf_notif_res = await send_workflow_notifications_task(workflow_execution_id=str(exec_id))
        assert wf_notif_res["status"] == "completed"
        assert wf_notif_res["workflow_execution_id"] == str(exec_id)

        # 4. Agent Notifications Task
        agent_id = uuid4()
        run_id = uuid4()
        async with session_factory() as session:
            agent = Agent(
                id=agent_id,
                organization_id=org_id,
                name="Financial Analyst",
                slug=f"agent-{agent_id.hex[:6]}",
                type="finance",
                status="active"
            )
            agent_run = AgentRun(
                id=run_id,
                organization_id=org_id,
                user_id=user_id,
                graph_name="financial_analyst",
                prompt="Analyze Q3 variance",
                status="completed",
                token_input=150,
                token_output=300,
                latency_ms=450,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None)
            )
            session.add_all([agent, agent_run])
            await session.commit()

        agent_notif_res = await send_agent_notifications_task(agent_execution_id=str(run_id))
        assert agent_notif_res["status"] == "completed"
        assert agent_notif_res["agent_execution_id"] == str(run_id)

    await engine.dispose()


@pytest.mark.asyncio
async def test_agent_tasks():
    """Verifies AI Agent task execution, fine-tuning, knowledge indexing, and performance optimization."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    agent_id = uuid4()

    async with session_factory() as session:
        org = Organization(
            id=org_id,
            name="AI Agent Test Org",
            slug=f"agentorg-{org_id.hex[:6]}",
            plan="enterprise",
            status="active"
        )
        user = User(
            id=user_id,
            tenant_id=org_id,
            email=f"ai-user-{uuid4().hex[:4]}@example.com",
            first_name="AI",
            last_name="Engineer",
            full_name="AI Engineer",
            password_hash="hashed_pw",
            status="active",
            is_active=True,
        )
        agent = Agent(
            id=agent_id,
            organization_id=org_id,
            name="Supply Chain Planner",
            slug=f"supply-planner-{agent_id.hex[:6]}",
            type="inventory",
            status="active",
            config={"temperature": 0.7, "max_tokens": 1500}
        )
        session.add_all([org, user, agent])
        await session.commit()

    # 1. Execute Agent Task
    exec_res = await execute_agent_task(
        agent_id=str(agent_id),
        user_id=str(user_id),
        input_data={"prompt": "Review warehouse safety stock levels"}
    )
    assert exec_res["status"] == "completed"
    assert exec_res["agent_id"] == str(agent_id)
    assert "result" in exec_res

    # 2. Train Agent Task
    train_res = await train_agent_task(
        agent_id=str(agent_id),
        training_data={
            "system_prompt": "You are an expert supply chain analyst prioritizing low stock alerts.",
            "examples": [{"input": "Stock low", "output": "Trigger purchase order"}]
        }
    )
    assert train_res["status"] == "completed"
    assert "system_prompt" in train_res["updated_config_keys"]

    # 3. Update Agent Knowledge Task
    know_res = await update_agent_knowledge_task(
        agent_id=str(agent_id),
        knowledge_updates=[
            {"id": f"doc-{uuid4()}", "content": "Warehouse A minimum reorder point is 500 units.", "department": "logistics"}
        ]
    )
    assert know_res["status"] == "completed"
    assert know_res["documents_indexed"] == 1

    # 4. Optimize Agent Performance Task
    opt_res = await optimize_agent_performance_task(
        agent_id=str(agent_id),
        performance_metrics={"high_latency": True, "hallucination_detected": True}
    )
    assert opt_res["status"] == "completed"
    assert opt_res["new_settings"]["temperature"] == 0.1
    assert opt_res["new_settings"]["max_tokens"] <= 1000

    await engine.dispose()


@pytest.mark.asyncio
async def test_workflow_tasks():
    """Verifies Workflow multi-step execution and scheduling against PostgreSQL."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    user_id = uuid4()
    wf_inv_id = uuid4()
    wf_fin_id = uuid4()

    async with session_factory() as session:
        org = Organization(
            id=org_id,
            name="Workflow Test Org",
            slug=f"wf-org-{org_id.hex[:6]}",
            plan="enterprise",
            status="active"
        )
        user = User(
            id=user_id,
            tenant_id=org_id,
            email=f"wf-user-{uuid4().hex[:4]}@example.com",
            first_name="Operations",
            last_name="Lead",
            full_name="Operations Lead",
            password_hash="hashed_pw",
            status="active",
            is_active=True,
        )
        wf_inv = Workflow(
            id=wf_inv_id,
            organization_id=org_id,
            name="Inventory Stock Health Check",
            slug=f"wf-inv-{wf_inv_id.hex[:6]}",
            category="inventory",
            created_by_id=user_id,
        )
        wf_fin = Workflow(
            id=wf_fin_id,
            organization_id=org_id,
            name="End of Month Revenue Reconcile",
            slug=f"wf-fin-{wf_fin_id.hex[:6]}",
            category="finance",
            created_by_id=user_id,
        )
        session.add_all([org, user, wf_inv, wf_fin])
        await session.commit()

    # 1. Execute Inventory Workflow
    inv_exec_res = await execute_workflow_task(
        workflow_id=str(wf_inv_id),
        user_id=str(user_id),
        input_data={"sku": "SKU-ALUM-8020"}
    )
    assert inv_exec_res["status"] == "completed"
    assert "inventory" in inv_exec_res["output"]["results"]

    # 2. Execute Finance Workflow
    fin_exec_res = await execute_workflow_task(
        workflow_id=str(wf_fin_id),
        user_id=str(user_id),
        input_data={}
    )
    assert fin_exec_res["status"] == "completed"
    assert "revenue" in fin_exec_res["output"]["results"]
    assert "pending_invoices" in fin_exec_res["output"]["results"]

    # 3. Schedule Workflow Task
    sched_res = await schedule_workflow_task(
        workflow_id=str(wf_inv_id),
        schedule_config={"cron": "0 8 * * 1-5", "timezone": "UTC"}
    )
    assert sched_res["status"] == "scheduled"
    assert sched_res["workflow_id"] == str(wf_inv_id)

    await engine.dispose()


@pytest.mark.asyncio
async def test_connector_tasks():
    """Verifies Connector health check and sync tasks."""
    engine = create_async_engine(ASYNC_TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    org_id = uuid4()
    integ_id = uuid4()
    conn_id = uuid4()

    async with session_factory() as session:
        org = Organization(
            id=org_id,
            name="Connector Test Org",
            slug=f"conn-org-{org_id.hex[:6]}",
            plan="enterprise",
            status="active"
        )
        integ = Integration(
            id=integ_id,
            organization_id=org_id,
            name="Custom REST Service",
            slug=f"rest-{integ_id.hex[:6]}",
            category="custom",
            provider="generic_rest",
            status="active"
        )
        session.add_all([org, integ])
        await session.commit()

    async with session_factory() as session:
        conn = IntegrationConnection(
            id=conn_id,
            integration_id=integ_id,
            connection_name="REST Main Endpoint",
            connection_type="rest",
            status="inactive",
            connection_config={"base_url": "https://api.example.com", "api_key": "test_key_123"},
        )
        session.add(conn)
        await session.commit()

    # Mock external HTTP network calls for connector health and sync
    with patch("packages.connectors.generic_rest.GenericRestConnector.test_connection", new_callable=AsyncMock) as mock_test, \
         patch("packages.connectors.generic_rest.GenericRestConnector.sync", new_callable=AsyncMock) as mock_sync:
        mock_test.return_value = {"status": "Healthy", "latency_ms": 25}
        mock_sync.return_value = {"records_synced": 42, "status": "completed"}

        # 1. Verify Connection Task
        verify_res = await verify_connection_task(connection_id=str(conn_id))
        assert verify_res["status"] == "success"
        assert verify_res["connection_id"] == str(conn_id)

        # 2. Sync Data Task
        sync_res = await sync_data_task(connection_id=str(conn_id))
        assert sync_res["status"] == "success"
        assert sync_res["connection_id"] == str(conn_id)
        assert sync_res["sync_result"]["records_synced"] == 42

    await engine.dispose()


@pytest.mark.asyncio
async def test_data_and_cleanup_tasks(tmp_path):
    """Verifies system metrics generation with psutil and cleanup file/log retention."""
    # 1. Real psutil system metrics
    sys_metrics = get_real_system_metrics()
    assert "cpu_usage_pct" in sys_metrics
    assert "memory_usage_pct" in sys_metrics
    assert "disk_free_gb" in sys_metrics
    assert isinstance(sys_metrics["cpu_usage_pct"], (int, float))

    # 2. Database Analytics & Telemetry Generation Task
    data_metrics_res = await generate_system_metrics_task(days=7, include_realtime=True)
    assert data_metrics_res["status"] == "completed"
    assert "overview" in data_metrics_res
    assert "system_telemetry" in data_metrics_res
    assert data_metrics_res["system_telemetry"]["cpu_usage_pct"] >= 0

    # 3. Retention Cleanup Task
    cleanup_res = await cleanup_old_executions_task(days=30)
    assert cleanup_res["status"] == "completed"
    assert cleanup_res["retention_days"] == 30

    # 4. Temp Files Cleanup Task
    test_temp_dir = tmp_path / "temp_files"
    test_temp_dir.mkdir()
    old_file = test_temp_dir / "old_temp.txt"
    old_file.write_text("temporary data")
    
    # Set modification time back 10 days
    past_ts = (datetime.now() - timedelta(days=10)).timestamp()
    os.utime(str(old_file), (past_ts, past_ts))

    temp_clean_res = cleanup_temp_files_task(temp_dir=str(test_temp_dir), older_than_days=7)
    assert temp_clean_res["status"] == "completed"
    assert temp_clean_res["files_deleted"] == 1
    assert not old_file.exists()

    # 5. Compress Logs Task
    test_log_dir = tmp_path / "logs"
    test_log_dir.mkdir()
    old_log = test_log_dir / "audit.log"
    old_log.write_text("2026-09-01 [INFO] Test audit log line")
    os.utime(str(old_log), (past_ts, past_ts))

    log_clean_res = compress_logs_task(log_dir=str(test_log_dir), older_than_days=7)
    assert log_clean_res["status"] == "completed"
    assert log_clean_res["files_compressed"] == 1
    assert not old_log.exists()
    assert (test_log_dir / "audit.log.gz").exists()
