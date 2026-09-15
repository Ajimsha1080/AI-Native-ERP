"""Database Seeder for Agentic ERP SaaS Platform."""
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import uuid
from datetime import datetime
from packages.database.core import session_scope, init_database
from packages.database.models import (
    Organization, Workspace, BusinessUnit, Team,
    User, UserRole, UserRoleAssignment, UserRoleType, UserStatus, AuthenticationProvider,
    Agent, AgentType, AgentStatus,
    Action, ActionType, ActionStatus, Approval,
    AuditEvent, AuditEventType,
    Connector, ConnectorConfig, ConnectorType, ConnectorStatus, SyncStatus,
    Workflow, WorkflowType, WorkflowStatus
)

DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_WS_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
DEFAULT_BU_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
DEFAULT_TEAM_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")
DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000005")


def seed_database():
    init_database()
    with session_scope() as session:
        # 1. Organization
        org = session.query(Organization).filter_by(id=DEFAULT_ORG_ID).first()
        if not org:
            org = Organization(
                id=DEFAULT_ORG_ID,
                name='Acme Global Enterprise',
                slug='acme-global',
                website='https://acme.com',
                email='admin@acme.com',
                status='active',
                plan='enterprise'
            )
            session.add(org)
            session.flush()

        # 2. Workspace
        ws = session.query(Workspace).filter_by(id=DEFAULT_WS_ID).first()
        if not ws:
            ws = Workspace(
                id=DEFAULT_WS_ID,
                tenant_id=DEFAULT_ORG_ID,
                organization_id=DEFAULT_ORG_ID,
                name='Global Operations',
                slug='global-operations',
                status='active',
                is_default=True
            )
            session.add(ws)

        # 3. Business Unit
        bu = session.query(BusinessUnit).filter_by(id=DEFAULT_BU_ID).first()
        if not bu:
            bu = BusinessUnit(
                id=DEFAULT_BU_ID,
                tenant_id=DEFAULT_ORG_ID,
                organization_id=DEFAULT_ORG_ID,
                name='Enterprise Systems',
                code='ENT-SYS',
                description='Core Enterprise Operations and Digital Systems'
            )
            session.add(bu)

        # 4. Team
        team = session.query(Team).filter_by(id=DEFAULT_TEAM_ID).first()
        if not team:
            team = Team(
                id=DEFAULT_TEAM_ID,
                tenant_id=DEFAULT_ORG_ID,
                organization_id=DEFAULT_ORG_ID,
                business_unit_id=DEFAULT_BU_ID,
                name='Executive Operations Core',
                slug='operations-core'
            )
            session.add(team)

        # 5. Role
        role = session.query(UserRole).filter_by(organization_id=DEFAULT_ORG_ID, slug='org-admin').first()
        if not role:
            role = UserRole(
                id=uuid.uuid4(),
                organization_id=DEFAULT_ORG_ID,
                name='Organization Admin',
                slug='org-admin',
                display_name='Organization Administrator',
                role_type=UserRoleType.ORGANIZATION_ADMIN,
                can_view_dashboard=True,
                can_access_settings=True,
                can_manage_users=True,
                can_manage_roles=True,
                can_manage_agents=True,
                can_execute_actions=True,
                can_approve_actions=True
            )
            session.add(role)
            session.flush()

        # 6. Admin User
        user = session.query(User).filter_by(email='admin@acme.com').first()
        if not user:
            user = User(
                id=DEFAULT_USER_ID,
                tenant_id=DEFAULT_ORG_ID,
                email='admin@acme.com',
                first_name='Admin',
                last_name='Executive',
                full_name='Admin Executive',
                title='Chief Operating Officer',
                department='Executive Office',
                is_active=True,
                is_verified=True,
                status=UserStatus.ACTIVE,
                provider=AuthenticationProvider.EMAIL
            )
            session.add(user)
            session.flush()

            ura = UserRoleAssignment(
                id=uuid.uuid4(),
                user_id=user.id,
                role_id=role.id,
                scope='organization',
                scope_id=DEFAULT_ORG_ID,
                assigned_by_id=user.id
            )
            session.add(ura)

        # 7. Domain Agents
        agents_def = [
            ('Finance Agent', 'finance-agent', AgentType.FINANCE, 'Autonomous Agent for real-time ledger management, revenue forecasting, AR/AP reconciliation, and cash flow operations.'),
            ('Inventory Agent', 'inventory-agent', AgentType.INVENTORY, 'Autonomous Agent for multi-warehouse SKU monitoring, stock velocity calculation, and reorder point optimization.'),
            ('Procurement Agent', 'procurement-agent', AgentType.PROCUREMENT, 'Autonomous Agent for purchase order drafting, vendor contract management, and RFP price matching.'),
            ('Sales Agent', 'sales-agent', AgentType.SALES, 'Autonomous Agent for CRM deal velocity tracking, pipeline revenue attribution, and churn risk detection.'),
            ('Operations Agent', 'operations-agent', AgentType.OPERATIONS, 'Autonomous Agent for freight logistics routing, supply chain lead time optimization, and order fulfillment.'),
            ('HR Agent', 'hr-agent', AgentType.HR, 'Autonomous Agent for workforce capacity planning, compliance audits, and internal policy inquiries.'),
            ('Analytics Agent', 'analytics-agent', AgentType.CUSTOM, 'Autonomous Agent for cross-departmental BI aggregation, executive metrics synthesis, and anomaly alerts.'),
            ('Compliance Agent', 'compliance-agent', AgentType.CUSTOM, 'Autonomous Agent for regulatory governance, financial audit trails, SOC2 policy enforcement, and AI guardrail checks.')
        ]

        for name, slug, agent_type, desc in agents_def:
            ag = session.query(Agent).filter_by(organization_id=DEFAULT_ORG_ID, slug=slug).first()
            if not ag:
                ag = Agent(
                    id=uuid.uuid4(),
                    organization_id=DEFAULT_ORG_ID,
                    workspace_id=DEFAULT_WS_ID,
                    business_unit_id=DEFAULT_BU_ID,
                    team_id=DEFAULT_TEAM_ID,
                    owner_id=user.id,
                    name=name,
                    slug=slug,
                    display_name=name,
                    type=agent_type,
                    status=AgentStatus.ACTIVE,
                    description=desc,
                    system_prompt=f'You are {name}, an autonomous AI specialist in enterprise operations.',
                    tools_enabled=True,
                    retrieval_enabled=True
                )
                session.add(ag)

        # 8. Initial Action & Approval demonstrating > $1,000 threshold
        existing_action = session.query(Action).filter_by(organization_id=DEFAULT_ORG_ID, name='PO-9021: Bulk Raw Materials Procurement').first()
        if not existing_action:
            procurement_agent = session.query(Agent).filter_by(slug='procurement-agent').first()
            sample_action = Action(
                id=uuid.uuid4(),
                organization_id=DEFAULT_ORG_ID,
                agent_id=procurement_agent.id if procurement_agent else None,
                requested_by_id=user.id,
                action_type=ActionType.CREATE,
                name='PO-9021: Bulk Raw Materials Procurement',
                description='Automated inventory replenishment triggered by low stock alert on SKU-ALUM-8020. Amount: $4,500.00 exceeds $1,000 threshold.',
                status=ActionStatus.APPROVAL_REQUIRED,
                requires_approval=True,
                action_data={'po_number': 'PO-9021', 'vendor': 'Apex Industrial Supplies', 'amount': 4500.00, 'items': [{'sku': 'SKU-ALUM-8020', 'qty': 500, 'unit_price': 9.00}]}
            )
            session.add(sample_action)
            session.flush()

            sample_approval = Approval(
                id=uuid.uuid4(),
                action_id=sample_action.id,
                approver_id=user.id,
                approver_role_id=role.id,
                status='pending',
                approval_type='financial',
                justification='Amount ($4,500.00) exceeds the autonomous threshold of $1,000.00.'
            )
            session.add(sample_approval)

        # 9. Initial Audit Events
        audit_events_data = [
            (AuditEventType.LOGIN, 'Admin Session Authenticated', 'Executive user admin@acme.com logged in with MFA verified.'),
            (AuditEventType.AGENT_EXECUTE, '8 Domain Agents Initialized', 'Workforce online and listening for automated ERP tasks across all business units.'),
            (AuditEventType.SECURITY_EVENT, 'AI Safety Boundaries Loaded', 'Prompt injection defense, PII masking, and $1,000 financial approval limits active.')
        ]
        for ev_type, ev_name, ev_desc in audit_events_data:
            existing_ev = session.query(AuditEvent).filter_by(organization_id=DEFAULT_ORG_ID, event_name=ev_name).first()
            if not existing_ev:
                ev = AuditEvent(
                    id=uuid.uuid4(),
                    organization_id=DEFAULT_ORG_ID,
                    user_id=user.id,
                    user_email='admin@acme.com',
                    user_role='Organization Admin',
                    event_type=ev_type,
                    event_name=ev_name,
                    description=ev_desc,
                    result='success'
                )
                session.add(ev)

        # 10. Sample Workflows
        wf_defs = [
            ('Automated Invoice Processing', 'automated-invoice-processing', 'finance', 'Extracts line items from received invoices, matches against purchase orders, and routes payments.'),
            ('Low-Stock Auto-Replenishment', 'low-stock-auto-replenishment', 'inventory', 'Monitors inventory reorder points and automatically drafts purchase orders when stock levels fall below safety thresholds.'),
            ('Vendor Contract Risk Review', 'vendor-contract-risk-review', 'procurement', 'Analyzes newly uploaded vendor agreements against standard liability caps and payment terms.')
        ]
        for wf_name, wf_slug, wf_cat, wf_desc in wf_defs:
            existing_wf = session.query(Workflow).filter_by(organization_id=DEFAULT_ORG_ID, slug=wf_slug).first()
            if not existing_wf:
                wf = Workflow(
                    id=uuid.uuid4(),
                    organization_id=DEFAULT_ORG_ID,
                    workspace_id=DEFAULT_WS_ID,
                    team_id=DEFAULT_TEAM_ID,
                    name=wf_name,
                    slug=wf_slug,
                    display_name=wf_name,
                    description=wf_desc,
                    category=wf_cat,
                    type=WorkflowType.AUTOMATED,
                    status=WorkflowStatus.ACTIVE
                )
                session.add(wf)

    print('Database seed complete!')


if __name__ == '__main__':
    seed_database()

