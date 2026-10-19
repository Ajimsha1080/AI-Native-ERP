"""
LangSmith Enterprise Observability & Tracing Manager.

Provides native integration with LangSmith for:
- LangGraph multi-agent execution tracing
- RAG pipeline observability and token accounting
- Multi-tenant contextual tagging (organization_id, user_id, user_role)
- Safe fallback when credentials are not configured or endpoint is unreachable
- Diagnostic health check and connection testing
"""

import os
from typing import Dict, Any, List, Optional
import structlog

from packages.config.settings import settings
from packages.security.guardrails import guardrails

logger = structlog.get_logger("observability.langsmith")


class LangSmithManager:
    """Manages LangSmith tracing client and environment configuration."""

    def __init__(self):
        self._client = None
        self._initialized = False

    def is_enabled(self) -> bool:
        """Checks if LangSmith tracing is enabled and configured with an API key."""
        return bool(
            settings.langchain_tracing_v2
            and settings.langchain_api_key
            and settings.langchain_api_key.strip()
            and not settings.langchain_api_key.startswith("your-")
        )

    def configure_tracing_environment(self) -> bool:
        """
        Configures environment variables required for LangChain / LangGraph automatic tracing.
        Should be called during application lifespan startup.
        """
        if self.is_enabled():
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key.strip()
            os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
            os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
            logger.info(
                "langsmith_tracing_configured",
                project=settings.langchain_project,
                endpoint=settings.langchain_endpoint,
            )
            self._initialized = True
            return True
        else:
            # Explicitly disable to prevent LangChain from making unauthorized network calls
            os.environ["LANGCHAIN_TRACING_V2"] = "false"
            if "LANGCHAIN_API_KEY" in os.environ and not os.environ["LANGCHAIN_API_KEY"]:
                del os.environ["LANGCHAIN_API_KEY"]
            self._initialized = False
            return False

    def get_client(self):
        """Returns the cached LangSmith Client instance if enabled, otherwise None."""
        if not self.is_enabled():
            return None

        if self._client is None:
            try:
                from langsmith import Client
                self._client = Client(
                    api_key=settings.langchain_api_key.strip(),
                    api_url=settings.langchain_endpoint,
                )
            except Exception as exc:
                logger.warning("langsmith_client_init_failed", error=str(exc))
                return None

        return self._client

    def get_tracing_callbacks(
        self,
        project_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Any]:
        """
        Returns LangChainTracer callback handler if LangSmith is enabled.
        Returns empty list when disabled so agent execution continues with zero overhead.
        """
        if not self.is_enabled():
            return []

        try:
            from langchain_core.tracers.langchain import LangChainTracer

            project = project_name or settings.langchain_project
            tracer = LangChainTracer(
                project_name=project,
                client=self.get_client(),
                tags=tags,
            )
            return [tracer]
        except Exception as exc:
            logger.warning("langsmith_tracer_callback_error", error=str(exc))
            return []

    def get_graph_run_config(
        self,
        organization_id: Any,
        user_id: Any,
        user_role: str,
        session_id: Optional[str] = None,
        graph_name: str = "erp_multi_agent",
        extra_tags: Optional[List[str]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Builds a LangGraph run configuration dict with multi-tenant tags and metadata.
        Automatically applies PCI-DSS / PII masking to prevent credential leakage into traces.
        """
        tags = ["agentic-erp", f"role:{user_role}", f"graph:{graph_name}"]
        if extra_tags:
            tags.extend(extra_tags)

        # Sanitize metadata to prevent card numbers or passwords from reaching traces
        raw_metadata = {
            "organization_id": str(organization_id),
            "user_id": str(user_id),
            "user_role": user_role,
            "session_id": session_id or "default",
            "graph_name": graph_name,
            "environment": settings.environment,
            **(extra_metadata or {}),
        }

        sanitized_metadata: Dict[str, Any] = {}
        for k, v in raw_metadata.items():
            if isinstance(v, str):
                sanitized_metadata[k] = guardrails.sanitize_pci_data(v)
            else:
                sanitized_metadata[k] = v

        config: Dict[str, Any] = {
            "tags": tags,
            "metadata": sanitized_metadata,
        }

        # Include explicit tracer callback if enabled
        callbacks = self.get_tracing_callbacks(
            project_name=settings.langchain_project,
            tags=tags,
            metadata=sanitized_metadata,
        )
        if callbacks:
            config["callbacks"] = callbacks

        return config

    def test_connection(self) -> Dict[str, Any]:
        """
        Runs diagnostic connection and authentication test against the LangSmith API.
        Safe for use in health/diagnostic status endpoints.
        """
        if not self.is_enabled():
            return {
                "status": "disabled",
                "configured": False,
                "project": settings.langchain_project,
                "endpoint": settings.langchain_endpoint,
                "message": (
                    "LangSmith tracing is disabled. Set LANGCHAIN_TRACING_V2=true "
                    "and provide LANGCHAIN_API_KEY to activate."
                ),
                "features": {
                    "langgraph_tracing": False,
                    "multi_tenant_tagging": False,
                    "rag_observability": False,
                },
            }

        client = self.get_client()
        if not client:
            return {
                "status": "error",
                "configured": True,
                "project": settings.langchain_project,
                "endpoint": settings.langchain_endpoint,
                "message": "Failed to instantiate LangSmith client.",
                "features": {
                    "langgraph_tracing": False,
                    "multi_tenant_tagging": False,
                    "rag_observability": False,
                },
            }

        try:
            # Check if project exists or is accessible
            has_proj = client.has_project(project_name=settings.langchain_project)
            return {
                "status": "connected",
                "configured": True,
                "project": settings.langchain_project,
                "endpoint": settings.langchain_endpoint,
                "project_exists": has_proj,
                "message": (
                    f"Successfully connected to LangSmith. "
                    f"Project '{settings.langchain_project}' {'is active' if has_proj else 'will be created on first trace'}."
                ),
                "features": {
                    "langgraph_tracing": True,
                    "multi_tenant_tagging": True,
                    "rag_observability": True,
                },
            }
        except Exception as exc:
            logger.warning("langsmith_connection_test_failed", error=str(exc))
            return {
                "status": "error",
                "configured": True,
                "project": settings.langchain_project,
                "endpoint": settings.langchain_endpoint,
                "message": f"LangSmith connection error: {str(exc)}",
                "features": {
                    "langgraph_tracing": False,
                    "multi_tenant_tagging": False,
                    "rag_observability": False,
                },
            }


# Singleton manager instance
langsmith_manager = LangSmithManager()
