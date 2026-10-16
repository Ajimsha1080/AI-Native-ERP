"""
Billing models: Processed Stripe Events for idempotency.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON
from packages.database.models.base import Base


class ProcessedStripeEvent(Base):
    """Tracks processed Stripe webhook event IDs for complete idempotency."""
    __tablename__ = "processed_stripe_events"

    id = Column(String(255), primary_key=True)  # Stripe event_id (e.g. evt_1N...)
    event_type = Column(String(100), nullable=False)
    processed_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )
    payload = Column(JSON, nullable=True)
