"""
Connector tasks.

Background tasks for external service connector operations:
- Real QuickBooks Online synchronization
- Generic REST API health checking & data syncing
- Exponential backoff retry loops
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID
import logging
import asyncio

from celery import shared_task
from sqlalchemy import select, update

from packages.database.core import async_session_scope
from packages.database.models import IntegrationConnection, Connector
from packages.connectors.quickbooks import QuickBooksConnector
from packages.connectors.generic_rest import GenericRestConnector
from packages.config import get_settings

logger = logging.getLogger("worker.connectors")
settings = get_settings()


def _get_connector_instance(connection_record: Any, connector_type: str) -> Any:
    """Instantiates the appropriate connector adapter class."""
    creds = connection_record.connection_config or {}
    tenant_id = "default_tenant"
    org_id = "default_org"

    if connector_type.lower() in ["quickbooks", "qbo"]:
        return QuickBooksConnector(tenant_id=tenant_id, organization_id=org_id, credentials=creds)
    else:
        return GenericRestConnector(tenant_id=tenant_id, organization_id=org_id, credentials=creds)


@shared_task(bind=True, name="connector.test_connection")
async def verify_connection_task(
    self,
    connection_id: str,
    test_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Tests connection health against live external endpoints."""
    start_time = datetime.now(timezone.utc)



    async with async_session_scope() as session:
        conn_res = await session.execute(
            select(IntegrationConnection).where(IntegrationConnection.id == UUID(connection_id))
        )
        conn = conn_res.scalar_one_or_none()
        if not conn:
            raise ValueError(f"IntegrationConnection {connection_id} not found")

        connector_type = str(conn.connection_type.value if hasattr(conn.connection_type, "value") else conn.connection_type)
        connector = _get_connector_instance(conn, connector_type)

        try:
            test_results = await connector.test_connection()
            is_healthy = test_results.get("status") in ["Healthy", "Connected"]
            conn.status = "active" if is_healthy else "failed"
            conn.last_tested_at = datetime.now(timezone.utc)
            conn.updated_at = datetime.now(timezone.utc)
            await session.commit()

            return {
                "status": "success" if is_healthy else "failed",
                "connection_id": connection_id,
                "provider": connector_type,
                "details": test_results,
                "test_time": (datetime.now(timezone.utc) - start_time).total_seconds()
            }
        except Exception as e:
            logger.error(f"Connection test failed for {connection_id}: {e}")
            conn.status = "failed"
            await session.commit()
            return {
                "status": "failed",
                "connection_id": connection_id,
                "error": str(e),
                "test_time": (datetime.now(timezone.utc) - start_time).total_seconds()
            }


test_connection_task = verify_connection_task
test_connection_task.__test__ = False



@shared_task(bind=True, name="connector.sync_data", max_retries=3)
async def sync_data_task(
    self,
    connection_id: str,
    sync_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Executes a real sync loop against the external connector with exponential backoff.
    """
    start_time = datetime.now(timezone.utc)

    async with async_session_scope() as session:
        conn_res = await session.execute(
            select(IntegrationConnection).where(IntegrationConnection.id == UUID(connection_id))
        )
        conn = conn_res.scalar_one_or_none()
        if not conn:
            raise ValueError(f"IntegrationConnection {connection_id} not found")

        connector_type = str(conn.connection_type.value if hasattr(conn.connection_type, "value") else conn.connection_type)
        connector = _get_connector_instance(conn, connector_type)

        # Retry loop with exponential backoff
        max_attempts = 3
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                sync_result = await connector.sync()
                
                conn.status = "active"
                conn.last_sync_at = datetime.now(timezone.utc)
                conn.updated_at = datetime.now(timezone.utc)
                await session.commit()

                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.info(f"Sync succeeded for connection {connection_id} on attempt {attempt}")
                return {
                    "status": "success",
                    "connection_id": connection_id,
                    "provider": connector_type,
                    "sync_result": sync_result,
                    "attempt": attempt,
                    "duration_seconds": duration
                }
            except Exception as e:
                last_error = e
                logger.warning(f"Sync attempt {attempt} failed for connection {connection_id}: {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(2 ** attempt)  # 2s, 4s backoff

        # If all attempts failed
        conn.status = "failed"
        await session.commit()
        return {
            "status": "failed",
            "connection_id": connection_id,
            "error": str(last_error),
            "attempts_made": max_attempts,
            "duration_seconds": (datetime.now(timezone.utc) - start_time).total_seconds()
        }