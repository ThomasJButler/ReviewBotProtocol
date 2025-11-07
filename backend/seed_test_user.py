"""Seed test user for development."""

import asyncio
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database.connection import init_db, get_db_session
from database.repositories.user_repository import UserRepository
from database.models import User
from config.logging import get_logger

logger = get_logger(__name__)


async def seed_test_user():
    """Create test user for development."""
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")

        # Get a database session
        async for session in get_db_session():
            user_repo = UserRepository(session)

            # Check if test user already exists
            existing_user = await user_repo.get_user_by_username("testuser")
            if existing_user:
                logger.info("Test user already exists")
                print("✅ Test user 'testuser' already exists!")
                return

            # Create test user
            test_user = User(
                username="testuser",
                email="test@example.com",
                name="Test User",
                github_id=0,  # Not a real GitHub user
                avatar_url="https://avatars.githubusercontent.com/u/0",
                is_active=True
            )

            # Add to database
            session.add(test_user)
            await session.commit()
            await session.refresh(test_user)

            logger.info(f"Test user created: {test_user.username} (ID: {test_user.id})")
            print(f"✅ Test user created successfully!")
            print(f"   Username: testuser")
            print(f"   Email: test@example.com")
            print(f"   Password: (any password works for testuser in DEBUG mode)")

    except Exception as e:
        logger.error(f"Failed to seed test user: {str(e)}")
        print(f"❌ Error: {str(e)}")
        raise


if __name__ == "__main__":
    print("🌱 Seeding test user for development...")
    asyncio.run(seed_test_user())
    print("✅ Done!")
