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

    # 3. Initialize ChromaDB Vector Store
    try:
        from packages.rag.vector_store import vector_store
        vector_store.get_or_create_collection("agentic_knowledge")
        logger.info("ChromaDB vector store initialized")
    except Exception as e:
        logger.warning(f"ChromaDB initialization note: {e}")

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

# Add request timing middleware
class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware to track request timing."""

    async def dispatch(self, request: Request, call_next):
        """Process request and measure timing.

        Args:
            request: FastAPI request
            call_next: Next middleware or route handler

        Returns:
            Response: Response from handler
        """
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate timing
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        # Log slow requests
        if process_time > 1.0:
            logger.warning(f"Slow request: {request.method} {request.url.path} - {process_time:.2f}s")

        return response

app.add_middleware(RequestTimingMiddleware)


# Health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }


# Root endpoint
@app.get("/", status_code=status.HTTP_200_OK)
async def root():
    """Root endpoint.

    Returns:
        dict: Welcome message
    """
    return {
        "message": "Welcome to Agentic Business Operating Platform",
        "version": settings.app_version,
        "environment": settings.environment,
        "docs": "/api/docs",
    }


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler.

    Args:
        request: FastAPI request
        exc: Exception

    Returns:
        JSONResponse: Error response
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if settings.environment == "development" else "An error occurred",
        },
    )


# Include routers
from apps.api.v1.routes import auth, users, agents, actions, organizations, tools, connectors, workflows, dashboard, webhooks, billing, knowledge
from apps.api.v1 import chat

# Include routers in order
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
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

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "apps.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
