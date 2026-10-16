#!/bin/bash

# Agentic ERP Backend Deployment Script

echo "🚀 Starting Agentic ERP Backend deployment..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p logs
mkdir -p temp
mkdir -p data
mkdir -p certs

# Set environment variables
export ENVIRONMENT=${ENVIRONMENT:-production}
export DATABASE_URL=${DATABASE_URL:-postgresql://admin:securepassword123@localhost:5432/agentic_erp}
export REDIS_URL=${REDIS_URL:-redis://localhost:6379}
export JWT_SECRET=${JWT_SECRET:-$(openssl rand -hex 32)}
export CELERY_BROKER_URL=${CELERY_BROKER_URL:-redis://localhost:6379}
export CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-redis://localhost:6379}

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📋 Creating environment file..."
    cat > .env << EOF
# Environment Configuration
ENVIRONMENT=${ENVIRONMENT}
DATABASE_URL=${DATABASE_URL}
REDIS_URL=${REDIS_URL}
JWT_SECRET=${JWT_SECRET}
CELERY_BROKER_URL=${CELERY_BROKER_URL}
CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}

# Security Settings
JWT_SECRET_KEY=${JWT_SECRET}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Worker Settings
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_LOGLEVEL=info
CELERY_WORKER_MAXTASKS=1000

# Security Settings
SECRET_KEY=${JWT_SECRET}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
EOF
fi

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

# Build and start the application
echo "🏗️ Building and starting the application..."
docker-compose up --build -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 30

# Check if all services are running
echo "🔍 Checking service status..."
docker-compose ps

# Wait for database migrations
echo "⏳ Running database migrations..."
sleep 10

# Initialize database if needed
echo "🗄️ Initializing database..."
python -c "
import asyncio
from packages.database.core import create_db_and_tables
async def main():
    await create_db_and_tables()
    print('Database initialized successfully')
asyncio.run(main())
"

# Check if database tables exist
echo "🔍 Checking database tables..."
python -c "
import asyncio
from packages.database.core import get_db
from packages.database.models import User
from sqlalchemy import text

async def main():
    async for db_session in get_db():
        result = await db_session.execute(text(\"SELECT COUNT(*) FROM users\"))
        count = result.scalar()
        print(f'Database tables exist. Users count: {count}')
asyncio.run(main())
"

# Start worker services
echo "🔄 Starting worker services..."
docker-compose restart worker
docker-compose restart beat

# Show logs
echo "📊 Starting log monitoring..."
echo "API Server: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo "Celery Worker Dashboard: http://localhost:5555"
echo ""
echo "🎉 Agentic ERP Backend deployment completed!"
echo ""
echo "Useful commands:"
echo "  - View logs: docker-compose logs -f"
echo "  - Stop services: docker-compose down"
echo "  - Restart services: docker-compose restart"
echo "  - Check status: docker-compose ps"