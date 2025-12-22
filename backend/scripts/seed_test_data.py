"""Seed database with test data for development."""
from sqlmodel import Session, select

from app.core.db import engine
from app.models import User, Item


def seed_test_data() -> None:
    """Create test users and items for development."""
    with Session(engine) as session:
        # Create test users (simulating OAuth-created users)
        test_users = [
            User(
                email="john.smith@example.com",
                username="jsmith",
                full_name="John Smith",
                active=True,
                admin=False,
            ),
            User(
                email="sarah.johnson@example.com",
                username="sjohnson",
                full_name="Sarah Johnson",
                active=True,
                admin=False,
            ),
            User(
                email="mike.chen@example.com",
                username="mchen",
                full_name="Mike Chen",
                active=True,
                admin=True,
            ),
        ]

        users_created = 0
        user_ids = {}  # Map username to id for creating items

        for user in test_users:
            # Check if user already exists by username
            existing_user = session.exec(
                select(User).where(User.username == user.username)
            ).first()
            if not existing_user:
                session.add(user)
                session.flush()  # Get the id without committing
                user_ids[user.username] = user.id
                users_created += 1
            else:
                user_ids[user.username] = existing_user.id

        session.commit()
        print(f"✅ Created {users_created} test users")

        # Create test items
        test_items = [
            Item(
                title="Data Processing Pipeline",
                description="Automated data processing pipeline for customer analytics. Handles ingestion, transformation, and storage of customer data.",
                owner_id=user_ids["jsmith"],
            ),
            Item(
                title="User Authentication Service",
                description="Centralized authentication service supporting OAuth 2.0, SAML, and multi-factor authentication.",
                owner_id=user_ids["sjohnson"],
            ),
            Item(
                title="Notification Engine",
                description="Real-time notification system supporting email, SMS, and push notifications.",
                owner_id=user_ids["mchen"],
            ),
            Item(
                title="Analytics Dashboard",
                description="Interactive dashboard for business intelligence and data visualization.",
                owner_id=user_ids["jsmith"],
            ),
            Item(
                title="API Gateway",
                description="Central API gateway for routing, rate limiting, and authentication of all API requests.",
                owner_id=user_ids["jsmith"],
            ),
            Item(
                title="File Storage Service",
                description="Distributed file storage service with encryption and redundancy.",
                owner_id=user_ids["sjohnson"],
            ),
            Item(
                title="Machine Learning Model",
                description="Customer churn prediction model using ensemble learning techniques.",
                owner_id=user_ids["mchen"],
            ),
            Item(
                title="Backup System",
                description="Automated backup system with incremental backups and disaster recovery capabilities.",
                owner_id=user_ids["sjohnson"],
            ),
        ]

        # Check if items already exist (by title)
        items_created = 0
        for item_data in test_items:
            existing_item = session.exec(
                select(Item).where(Item.title == item_data.title)
            ).first()
            if not existing_item:
                session.add(item_data)
                items_created += 1

        session.commit()
        print(f"✅ Created {items_created} test items")


if __name__ == "__main__":
    seed_test_data()
