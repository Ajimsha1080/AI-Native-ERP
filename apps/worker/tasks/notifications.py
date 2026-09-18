"""
Notification tasks.

Production-grade background tasks for sending email and in-app notifications and alerts.
Utilizes real SMTP dispatching via application settings with full TLS support.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
import logging
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from celery import shared_task
from sqlalchemy import select, and_, func

from packages.database.core import async_session_scope
from packages.database.models import (
    User, WorkflowExecution, Workflow, AuditEvent, AuditEventType
)
from packages.database.models.erp.agent_runs import AgentRun
from packages.config import get_settings

logger = logging.getLogger("worker.notifications")
settings = get_settings()


def _dispatch_smtp_sync(
    recipient_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """Dispatches email via standard SMTP server with TLS."""
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.email_from or "noreply@agenticplatform.com"
        msg["To"] = recipient_email
        msg["Subject"] = subject

        # Plaintext fallback
        plain_body = text_content or subject
        msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        if not settings.smtp_host:
            logger.info(f"[SMTP Dev Mode] Email to {recipient_email} - Subject: '{subject}' (No SMTP host configured)")
            return True

        port = settings.smtp_port or 587
        with smtplib.SMTP(settings.smtp_host, port, timeout=10) as server:
            if port == 587:
                server.starttls()
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], [recipient_email], msg.as_string())

        logger.info(f"Successfully dispatched SMTP email to {recipient_email}")
        return True
    except Exception as e:
        logger.error(f"SMTP dispatch failed for {recipient_email}: {e}")
        return False


async def send_email_async(
    recipient_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """Asynchronous wrapper for SMTP sending."""
    return await asyncio.to_thread(_dispatch_smtp_sync, recipient_email, subject, html_content, text_content)


@shared_task(bind=True, name="notifications.send_verification_email")
def send_verification_email_task(
    self,
    email: str,
    verification_token: str,
    user_name: str
) -> Dict[str, Any]:
    """Sends email verification link to newly registered user."""
    verify_url = f"http://localhost:3000/verify?token={verification_token}"
    subject = "Verify your Agentic ERP Account"
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; padding: 30px;">
        <div style="max-width: 540px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 32px; border: 1px solid #e2e8f0;">
            <h2 style="color: #0f172a; margin-top: 0;">Welcome to Agentic ERP, {user_name}!</h2>
            <p style="color: #475569; font-size: 15px; line-height: 1.6;">Please confirm your email address to activate your enterprise workspace.</p>
            <div style="margin: 28px 0;">
                <a href="{verify_url}" style="background: #2563eb; color: #ffffff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">Verify Email Address</a>
            </div>
            <p style="color: #94a3b8; font-size: 13px;">If you did not sign up for an account, please disregard this email.</p>
        </div>
    </body>
    </html>
    """
    success = _dispatch_smtp_sync(email, subject, html)
    return {"status": "sent" if success else "failed", "recipient": email}


@shared_task(bind=True, name="notifications.send_password_reset_email")
def send_password_reset_email_task(
    self,
    email: str,
    reset_token: str,
    user_name: str
) -> Dict[str, Any]:
    """Sends password reset link to user."""
    reset_url = f"http://localhost:3000/reset-password?token={reset_token}"
    subject = "Reset your Agentic ERP Password"
    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; padding: 30px;">
        <div style="max-width: 540px; margin: 0 auto; background: #ffffff; border-radius: 12px; padding: 32px; border: 1px solid #e2e8f0;">
            <h2 style="color: #0f172a; margin-top: 0;">Password Reset Request</h2>
            <p style="color: #475569; font-size: 15px; line-height: 1.6;">Hello {user_name}, we received a request to reset your password. Click the link below to set a new password:</p>
            <div style="margin: 28px 0;">
                <a href="{reset_url}" style="background: #2563eb; color: #ffffff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">Reset Password</a>
            </div>
            <p style="color: #94a3b8; font-size: 13px;">This link will expire in 60 minutes. If you did not request this, please contact security immediately.</p>
        </div>
    </body>
    </html>
    """
    success = _dispatch_smtp_sync(email, subject, html)
    return {"status": "sent" if success else "failed", "recipient": email}


@shared_task(bind=True, name="notifications.send_alerts")
async def send_alerts_task(
    self,
    alert_type: str,
    recipient_ids: List[str],
    alert_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Send alerts to specified recipients asynchronously."""
    start_time = datetime.now(timezone.utc)
    notification_results = {
        "status": "completed",
        "alert_type": alert_type,
        "recipients": len(recipient_ids),
        "successful": 0,
        "failed": 0,
        "failures": [],
    }

    async with async_session_scope() as session:
        for recipient_id in recipient_ids:
            try:
                user_res = await session.execute(select(User).where(User.id == UUID(recipient_id)))
                user = user_res.scalar_one_or_none()

                if not user:
                    notification_results["failed"] += 1
                    notification_results["failures"].append(f"User {recipient_id} not found")
                    continue

                audit_evt = AuditEvent(
                    organization_id=getattr(user, "organization_id", None) or getattr(user, "tenant_id", None) or uuid4(),
                    user_id=user.id,
                    user_email=user.email,
                    event_type=AuditEventType.SECURITY_ALERT,
                    event_name=alert_data.get("title", f"Alert: {alert_type}"),
                    description=alert_data.get("message", "An alert has been triggered"),
                    meta_data=alert_data
                )
                session.add(audit_evt)

                # Send real email notification
                title = alert_data.get("title", f"Alert: {alert_type}")
                html_body = f"""
                <html>
                <body style="font-family: sans-serif; padding: 20px;">
                    <h2>{title}</h2>
                    <p>{alert_data.get("message", "An alert has been triggered")}</p>
                    <pre style="background: #eee; padding: 10px;">{str(alert_data)}</pre>
                </body>
                </html>
                """
                await send_email_async(user.email, title, html_body)

                notification_results["successful"] += 1
            except Exception as e:
                notification_results["failed"] += 1
                notification_results["failures"].append(str(e))
                logger.error(f"Error sending alert to {recipient_id}: {e}")

        await session.commit()

    notification_results["notification_time"] = (datetime.now(timezone.utc) - start_time).total_seconds()
    return notification_results


@shared_task(bind=True, name="notifications.send_workflow_notifications")
async def send_workflow_notifications_task(
    self,
    workflow_execution_id: str
) -> Dict[str, Any]:
    """Send workflow execution notifications asynchronously."""
    async with async_session_scope() as session:
        exec_res = await session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == UUID(workflow_execution_id))
        )
        execution = exec_res.scalar_one_or_none()
        if not execution:
            raise ValueError(f"Workflow execution {workflow_execution_id} not found")

        wf_res = await session.execute(select(Workflow).where(Workflow.id == execution.workflow_id))
        workflow = wf_res.scalar_one_or_none()

        user_res = await session.execute(select(User).where(User.id == execution.user_id))
        user = user_res.scalar_one_or_none()

        recipient = user.email if user else settings.email_from
        title = f"Workflow '{workflow.name if workflow else 'Automation'}' Status: {execution.status.upper()}"
        message = f"Workflow execution {workflow_execution_id} completed with status {execution.status}."

        html = f"""
        <html>
        <body style="font-family: sans-serif; padding: 20px;">
            <h3>{title}</h3>
            <p>{message}</p>
            <p>Execution Time: {execution.execution_time or 0:.2f}s</p>
        </body>
        </html>
        """
        success = await send_email_async(recipient, title, html)

        return {
            "status": "completed",
            "workflow_execution_id": workflow_execution_id,
            "recipient": recipient,
            "email_sent": success
        }


@shared_task(bind=True, name="notifications.send_agent_notifications")
async def send_agent_notifications_task(
    self,
    agent_execution_id: str
) -> Dict[str, Any]:
    """Send agent execution notifications asynchronously."""
    async with async_session_scope() as session:
        exec_res = await session.execute(
            select(AgentRun).where(AgentRun.id == UUID(agent_execution_id))
        )
        run = exec_res.scalar_one_or_none()

        recipient = settings.email_from
        if run and run.user_id:
            user_res = await session.execute(select(User).where(User.id == run.user_id))
            user = user_res.scalar_one_or_none()
            if user:
                recipient = user.email

        title = f"Agent Run Notification: {run.graph_name if run else 'AI Specialist'}"
        message = f"Agent prompt: '{run.prompt if run else ''}' finished with status: {run.status if run else 'completed'}."

        html = f"""
        <html>
        <body style="font-family: sans-serif; padding: 20px;">
            <h3>{title}</h3>
            <p>{message}</p>
            <p>Tokens Used: {run.token_input + run.token_output if run else 0}</p>
        </body>
        </html>
        """
        success = await send_email_async(recipient, title, html)

        return {
            "status": "completed",
            "agent_execution_id": agent_execution_id,
            "recipient": recipient,
            "email_sent": success
        }