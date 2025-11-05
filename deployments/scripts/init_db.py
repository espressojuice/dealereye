#!/usr/bin/env python3
"""
Initialize DealerEye database with schema and sample data.
Run this after starting PostgreSQL with Docker Compose.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from control-plane.storage.database import (
    create_database_engine,
    init_database,
    create_hypertables,
    TenantModel,
    SiteModel,
    UserModel,
)
from shared.config import ControlPlaneConfig
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    """Initialize database schema."""
    config = ControlPlaneConfig()
    engine = create_database_engine(config.DATABASE_URL)

    logger.info("Creating database schema...")
    init_database(engine)
    logger.info("Database schema created")

    logger.info("Creating TimescaleDB hypertables...")
    try:
        create_hypertables(engine)
        logger.info("Hypertables created")
    except Exception as e:
        logger.warning(f"Could not create hypertables (may not be using TimescaleDB): {e}")

    logger.info("Database initialization complete!")


def create_sample_data():
    """Create sample tenant and site for development."""
    from uuid import uuid4
    from datetime import time
    from sqlalchemy.orm import Session

    config = ControlPlaneConfig()
    engine = create_database_engine(config.DATABASE_URL)

    with Session(engine) as session:
        # Create sample tenant
        tenant_id = uuid4()
        tenant = TenantModel(
            tenant_id=tenant_id,
            name="Texarkana Auto Group",
            settings={},
        )
        session.add(tenant)

        # Create sample site
        site_id = uuid4()
        site = SiteModel(
            site_id=site_id,
            tenant_id=tenant_id,
            name="Texarkana Toyota",
            timezone="America/Chicago",
            address="123 Main St, Texarkana, TX 75501",
            business_hours={
                "open_time": "08:00:00",
                "close_time": "18:00:00",
                "days_of_week": [0, 1, 2, 3, 4, 5],  # Mon-Sat
            },
            settings={},
        )
        session.add(site)

        # Create sample admin user
        from passlib.hash import bcrypt
        user = UserModel(
            user_id=uuid4(),
            tenant_id=tenant_id,
            email="admin@texarkanauto.com",
            name="Admin User",
            role="tenant_admin",
            password_hash=bcrypt.hash("changeme123"),
            site_ids=[str(site_id)],
        )
        session.add(user)

        session.commit()

        logger.info("Sample data created:")
        logger.info(f"  Tenant ID: {tenant_id}")
        logger.info(f"  Site ID: {site_id}")
        logger.info(f"  Admin email: admin@texarkanauto.com")
        logger.info(f"  Admin password: changeme123")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Initialize DealerEye database")
    parser.add_argument(
        "--sample-data",
        action="store_true",
        help="Create sample tenant and site",
    )
    args = parser.parse_args()

    init_db()

    if args.sample_data:
        logger.info("Creating sample data...")
        create_sample_data()
