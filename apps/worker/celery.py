"""
Celery Application Instance for AI-Native ERP Worker.

Configured for production-grade task execution with Redis broker/backend,
rate limiting, task persistence, beat scheduling, and automatic retries.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Determine broker and backend dynamically from environment or settings
broker_url = (
    os.getenv("CELERY_BROKER_URL")
    or os.getenv("REDIS_URL")
    or "redis://localhost:6379/0"
)
backend_url = (
    os.getenv("CELERY_RESULT_BACKEND")
    or os.getenv("REDIS_URL")
    or "redis://localhost:6379/0"
)

celery_app = Celery(
    "worker",
    broker=broker_url,
    backend=backend_url,
    include=[
        "apps.worker.tasks.agents",
        "apps.worker.tasks.tools",
        "apps.worker.tasks.connectors",
        "apps.worker.tasks.workflows",
        "apps.worker.tasks.data",
        "apps.worker.tasks.notifications",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_reject_on_worker_lost=True,
    worker_hijack_root_logger=False,
    worker_log_color=False,
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_id)s] %(message)s",
    task_annotations={
        "apps.worker.tasks.agents.*": {
            "rate_limit": "10/m",
        },
        "apps.worker.tasks.tools.*": {
            "rate_limit": "30/m",
        },
        "apps.worker.tasks.connectors.*": {
            "rate_limit": "20/m",
        },
        "apps.worker.tasks.workflows.*": {
            "rate_limit": "5/m",
        },
        "apps.worker.tasks.data.*": {
            "rate_limit": "15/m",
        },
        "apps.worker.tasks.notifications.*": {
            "rate_limit": "100/m",
        },
    },
    beat_schedule={
        "cleanup-logs": {
            "task": "apps.worker.tasks.cleanup.cleanup_old_logs",
            "schedule": crontab(minute=0, hour=0),  # Daily at midnight
        },
        "cleanup-temp-files": {
            "task": "apps.worker.tasks.cleanup.cleanup_temp_files",
            "schedule": crontab(minute=0, hour=3),  # Daily at 3 AM
        },
        "update-stats": {
            "task": "apps.worker.tasks.stats.update_usage_stats",
            "schedule": crontab(minute=0, hour=1),  # Daily at 1 AM
        },
        "check-health": {
            "task": "apps.worker.tasks.health.check_system_health",
            "schedule": crontab(minute=0, hour=6),  # Daily at 6 AM
        },
    },
    beat_schedule_filename="/tmp/celerybeat-schedule",  # nosec B108
)

if __name__ == "__main__":
    celery_app.start()
