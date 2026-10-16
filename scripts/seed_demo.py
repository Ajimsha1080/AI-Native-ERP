"""Explicit CLI script to seed demo data. Refused in production and staging."""
import os
import sys
import asyncio
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from packages.config.settings import settings
from packages.database.seed_demo import seed_demo_accounts

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("scripts.seed_demo")

def main():
    env = os.getenv("ENVIRONMENT", settings.environment).strip().lower()
    if env in ("production", "prod", "staging", "stage"):
        logger.error(f"FATAL: Demo data seeding is strictly refused in '{env}' environment!")
        sys.exit(1)

    logger.info(f"Starting explicit demo data seeding for environment: {env}")
    try:
        asyncio.run(seed_demo_accounts())
        logger.info("Demo data seeding completed successfully.")
    except Exception as e:
        logger.error(f"Demo seeding failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
