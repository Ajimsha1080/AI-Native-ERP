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
from packages.database import get_db, create_db_and_tables
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

    # 1. Create database tables if needed
    await create_db_and_tables()
    logger.info("Database tables verified and ready")

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

    # 3. Initialize PostgreSQL pgvector Store
    try:
        from packages.rag.vector_store import vector_store
        logger.info("PostgreSQL pgvector store initialized")
    except Exception as e:
        logger.warning(f"PostgreSQL pgvector initialization note: {e}")

    # 4. Initialize AI Guardrails & Agent Core
    try:
        from packages.security.guardrails import guardrails
        logger.info(f"AI Guardrail Engine active with ${guardrails.max_auto_approval_limit:,.2f} approval gate")
    except Exception as e:
        logger.warning(f"AI Guardrails initialization note: {e}")

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
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    root_path="" if settings.environment == "development" else "/api",
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

# Prometheus metrics collector
from fastapi.responses import PlainTextResponse
from collections import defaultdict
import threading
import re

class PrometheusMetricsTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self.request_counts = defaultdict(int)
        self.request_durations = defaultdict(list)
        self.agent_runs = defaultdict(int)

    def record_request(self, method: str, path: str, status_code: int, duration: float):
        endpoint = path.split("?")[0]
        # Normalize UUIDs in paths for metrics grouping
        normalized_path = re.sub(r'/[0-9a-fA-F-]{36}', '/:id', endpoint)
        with self._lock:
            key = (method, normalized_path, str(status_code))
            self.request_counts[key] += 1
            if len(self.request_durations[(method, normalized_path)]) < 500:
                self.request_durations[(method, normalized_path)].append(duration)

    def generate_metrics_text(self) -> str:
        lines = [
            "# HELP http_requests_total Total number of HTTP requests processed",
            "# TYPE http_requests_total counter",
        ]
        with self._lock:
            for (method, path, sc), count in self.request_counts.items():
                lines.append(f'http_requests_total{{method="{method}",endpoint="{path}",status="{sc}"}} {count}')
            
            lines.extend([
                "# HELP http_request_duration_seconds HTTP request latency summary in seconds",
                "# TYPE http_request_duration_seconds summary",
            ])
            for (method, path), durations in self.request_durations.items():
                if durations:
                    avg_dur = sum(durations) / len(durations)
                    lines.append(f'http_request_duration_seconds_sum{{method="{method}",endpoint="{path}"}} {sum(durations):.4f}')
                    lines.append(f'http_request_duration_seconds_count{{method="{method}",endpoint="{path}"}} {len(durations)}')
                    lines.append(f'http_request_duration_seconds{{method="{method}",endpoint="{path}",quantile="0.5"}} {avg_dur:.4f}')

        return "\n".join(lines) + "\n"

metrics_tracker = PrometheusMetricsTracker()


# Add request timing and metrics middleware
class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware to track request timing and metrics."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}"

        # Record metrics
        metrics_tracker.record_request(request.method, request.url.path, response.status_code, process_time)

        if process_time > 1.0:
            logger.warning(f"Slow request: {request.method} {request.url.path} - {process_time:.2f}s")

        return response

app.add_middleware(RequestTimingMiddleware)


# Prometheus Metrics endpoint
@app.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint():
    """Prometheus exposition metrics endpoint for system observability."""
    return metrics_tracker.generate_metrics_text()


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
    inventory, sales, purchasing, accounting, hr, approvals, jobs, compliance
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

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "apps.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )

