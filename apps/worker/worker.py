"""
Worker main application.

Entry point for the Celery worker.
"""

import logging
import os
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('worker.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Import Celery app
from apps.worker import celery_app

if __name__ == '__main__':
    # Start the Celery worker
    logger.info("Starting Celery worker...")
    
    # Get worker configuration from environment
    concurrency = int(os.getenv('CELERY_WORKER_CONCURRENCY', '4'))
    loglevel = os.getenv('CELERY_WORKER_LOGLEVEL', 'info')
    maxtasksperchild = int(os.getenv('CELERY_WORKER_MAXTASKS', '1000'))
    
    # Configure worker settings
    worker_args = [
        '--loglevel=' + loglevel,
        '--concurrency=' + str(concurrency),
        '--maxtasksperchild=' + str(maxtasksperchild),
        '--logfile=worker.log',
        '--pidfile=worker.pid'
    ]
    
    # Start worker with configured settings
    celery_app.worker_main(argv=worker_args)