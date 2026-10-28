"""
Main FastAPI application.

The entry point for the Agentic Business Operating Platform API.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging
import asyncio

from packages.config import get_settings
from packages.database import (
    get_db, create_db_and_tables, create_rls_policies, assert_rls_policies_active
)
from packages.database.core import is_sqlite
from packages.security import SecurityMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events for Database, Redis, Celery, Vector Store, and AI engines.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version} in {settings.environment} mode")

    # 1. Verify Row-Level Security (RLS) policies are active on all tenant tables (PostgreSQL only)
    if not is_sqlite:
        await assert_rls_policies_active()
        logger.info("PostgreSQL Row-Level Security (RLS) policies verified active")

    # 2. Initialize Redis connection
    redis_client = None
    try:
        import redis.asyncio as aioredis
        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        # Quick non-blocking ping
        await asyncio.wait_for(redis_client.ping(), timeout=1.0)
        logger.info(f"Redis cache connected at {settings.redis_url}")
    except Exception as e:
        logger.info(f"Redis connection skipped ({e}). Using in-memory fallback cache.")
        redis_client = None

    # 3. Initialize & Validate Embedding Configuration and Vector Store
    try:
        from packages.rag.embedding_service import embedding_service
        from packages.rag.vector_store import vector_store
        if settings.embedding_dimension != embedding_service.dimension:
            raise RuntimeError(
                f"Embedding dimension mismatch: settings={settings.embedding_dimension} "
                f"!= embedding_service={embedding_service.dimension}"
            )
        if settings.embedding_dimension != vector_store.dimension:
            raise RuntimeError(
                f"Vector store dimension mismatch: settings={settings.embedding_dimension} "
                f"!= vector_store={vector_store.dimension}"
            )
        logger.info(
            f"PostgreSQL pgvector & embedding engine validated: "
            f"model='{settings.embedding_model}', dimension={settings.embedding_dimension}"
        )
    except Exception as e:
        logger.error(f"Embedding/pgvector startup validation failed: {e}")
        raise

    # 4. Initialize AI Guardrails & Agent Core
    try:
        from packages.security.guardrails import guardrails
        logger.info(f"AI Guardrail Engine active with ${guardrails.max_auto_approval_limit:,.2f} approval gate")
    except Exception as e:
        logger.warning(f"AI Guardrails initialization note: {e}")

    # 5. Verify Stripe Billing Configuration (fail-fast in production)
    from packages.billing.stripe_client import validate_stripe_configuration
    validate_stripe_configuration()
    logger.info("Stripe billing configuration verified")

    # 6. Initialize Sentry APM (if configured)
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                traces_sample_rate=settings.sentry_traces_sample_rate,
            )
            logger.info(f"Sentry APM initialized in {settings.environment} mode")
        except Exception as e:
            logger.warning(f"Sentry initialization note: {e}")

    # 7. Initialize OpenTelemetry (if configured)
    if settings.otel_exporter_otlp_endpoint and settings.environment != "test":
        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.resources import Resource
            resource = Resource.create({"service.name": settings.otel_service_name, "environment": settings.environment})
            provider = TracerProvider(resource=resource)
            trace.set_tracer_provider(provider)
            logger.info(f"OpenTelemetry initialized for service {settings.otel_service_name}")
        except Exception as e:
            logger.info(f"OpenTelemetry initialization note: {e}")

    # 8. Initialize LangSmith Agent Tracing & Observability (if configured)
    from packages.observability.langsmith_client import langsmith_manager
    if langsmith_manager.configure_tracing_environment():
        logger.info(f"LangSmith agent tracing active on project '{settings.langchain_project}'")
    else:
        logger.info("LangSmith tracing is disabled (set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY to activate)")

    logger.info(f"{settings.app_name} started successfully")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")

    if redis_client:
        try:
            await redis_client.close()
            logger.info("Redis connection closed cleanly")
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {e}")

    logger.info(f"{settings.app_name} shutdown complete")



# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Enterprise-grade AI-Native Business Operating Platform",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    root_path=settings.root_path,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add GZip middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add security middleware
app.add_middleware(SecurityMiddleware)

# Official Prometheus metrics collector
from prometheus_client import REGISTRY, Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import re


def _get_or_create_counter(name, doc, labelnames):
    if name in REGISTRY._names_to_collectors:
        return REGISTRY._names_to_collectors[name]
    return Counter(name, doc, labelnames)


def _get_or_create_histogram(name, doc, labelnames, buckets):
    if name in REGISTRY._names_to_collectors:
        return REGISTRY._names_to_collectors[name]
    return Histogram(name, doc, labelnames, buckets=buckets)


HTTP_REQUESTS_TOTAL = _get_or_create_counter(
    "http_requests_total",
    "Total number of HTTP requests processed",
    ["method", "endpoint", "status"]
)

HTTP_REQUEST_DURATION_SECONDS = _get_or_create_histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
)



# Add request timing and metrics middleware
class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware to track request timing and metrics."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}"

        # Record metrics using official prometheus-client
        endpoint = request.url.path.split("?")[0]
        normalized_path = re.sub(r'/[0-9a-fA-F-]{36}', '/:id', endpoint)
        try:
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=normalized_path,
                status=str(response.status_code)
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=request.method,
                endpoint=normalized_path
            ).observe(process_time)
        except Exception:
            pass

        if process_time > 1.0:
            logger.warning(f"Slow request: {request.method} {request.url.path} - {process_time:.2f}s")

        return response

app.add_middleware(RequestTimingMiddleware)


# Prometheus Metrics endpoint
@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus exposition metrics endpoint for system observability."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Liveness probe returning basic service health."""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


# Readiness check endpoint
@app.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check():
    """Readiness probe checking database connectivity."""
    db_status = "healthy"
    try:
        from packages.database.core import async_session_scope
        from sqlalchemy import text
        async with async_session_scope() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {e}"

    is_ready = "unhealthy" not in db_status
    status_code = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if is_ready else "not_ready",
            "database": db_status,
            "app_name": settings.app_name,
            "version": settings.app_version,
        }
    )


# Root endpoint
@app.get("/", status_code=status.HTTP_200_OK)
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to Agentic Business Operating Platform",
        "version": settings.app_version,
        "environment": settings.environment,
        "docs": "/api/docs",
    }


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if settings.environment == "development" else "An error occurred",
        },
    )


# Include routers
from apps.api.v1.routes import (
    auth, users, agents, actions, organizations, tools, connectors,
    workflows, dashboard, webhooks, billing, knowledge,
    inventory, sales, purchasing, accounting, hr, approvals, jobs, compliance, tts
)
from apps.api.v1 import chat

# Include routers in order
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(inventory.router, prefix="/api/v1")
app.include_router(sales.router, prefix="/api/v1")
app.include_router(purchasing.router, prefix="/api/v1")
app.include_router(accounting.router, prefix="/api/v1")
app.include_router(hr.router, prefix="/api/v1")
app.include_router(approvals.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(actions.router, prefix="/api/v1")
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")
app.include_router(connectors.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(compliance.router, prefix="/api/v1")
app.include_router(tts.router, prefix="/api/v1")

from fastapi.responses import RedirectResponse

@app.get("/api/docs", include_in_schema=False)
async def api_docs_redirect():
    return RedirectResponse(url="/docs")

@app.get("/api/openapi.json", include_in_schema=False)
async def api_openapi_redirect():
    return RedirectResponse(url="/openapi.json")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "apps.api.main:app",
        host="0.0.0.0",  # nosec B104
        port=8000,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )

