"""
Worker service.

Background task processing using Celery.
"""

from apps.worker.celery import celery_app

__all__ = ["celery_app"]

if __name__ == "__main__":
    celery_app.start()