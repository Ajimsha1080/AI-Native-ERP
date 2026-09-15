from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from packages.config import get_settings
from apps.api.v1.chat import router as chat_router
from apps.api.v1.routes.dashboard import router as dashboard_router
from packages.agents.api import router as agents_router
from packages.agents.database import engine, Base

settings = get_settings()

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Agentic ERP Development Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from apps.api.v1.routes.connectors import router as connectors_router
from apps.api.v1.routes.webhooks import router as webhooks_router
from apps.api.v1.routes.auth import router as auth_router

app.include_router(chat_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(connectors_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
