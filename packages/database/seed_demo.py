"""Auto-seeder for development and demo accounts."""
import logging
from sqlalchemy import select
from packages.database.core import AsyncSessionLocal
from packages.database.models.organization import Organization
from packages.database.models.user import User, UserStatus, AuthenticationProvider
from packages.auth.password import hash_password

logger = logging.getLogger(__name__)

async def ensure_demo_users():
    """Idempotently ensure default organization and demo users exist."""
    async with AsyncSessionLocal() as session:
        try:
            # 1. Check or create default organization
            org_res = await session.execute(select(Organization).limit(1))
            org = org_res.scalar_one_or_none()
            if not org:
                org = Organization(
                    name="Acme Industrial Corp",
                    slug="acme-industrial",
                    email="contact@acmeindustrial.com",
                    plan="enterprise",
                )
                session.add(org)
                await session.flush()

            users_to_seed = [
                ("admin@acmeindustrial.com", "Admin", "User", "Admin Executive"),
                ("manager@acmeindustrial.com", "Operations", "Manager", "Operations Manager"),
                ("viewer@acmeindustrial.com", "Auditor", "Viewer", "Readonly Viewer"),
            ]

            hashed = hash_password("password123")

            for email, first, last, title in users_to_seed:
                res = await session.execute(select(User).where(User.email == email))
                existing = res.scalar_one_or_none()
                if not existing:
                    u = User(
                        email=email,
                        first_name=first,
                        last_name=last,
                        full_name=f"{first} {last}",
                        title=title,
                        password_hash=hashed,
                        tenant_id=org.id,
                        is_active=True,
                        is_verified=True,
                        status=UserStatus.ACTIVE,
                        provider=AuthenticationProvider.EMAIL,
                    )
                    session.add(u)
                    logger.info(f"Seeded demo account: {email}")
                else:
                    if not existing.password_hash or not existing.is_active:
                        existing.password_hash = hashed
                        existing.is_active = True
                        existing.is_verified = True

            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.warning(f"ensure_demo_users note: {e}")
