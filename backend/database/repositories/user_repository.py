"""Repository for managing user data access."""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from datetime import datetime
import uuid

from ..models import User, ApiKey
from config.logging import get_logger
from utils.helpers import get_utc_timestamp

logger = get_logger(__name__)


class UserRepository:
    """Repository for user operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(self, user_data: Dict[str, Any]) -> User:
        """Create a new user."""
        try:
            user = User(**user_data)
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)

            logger.info(f"Created user {user.username}")
            return user

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create user: {str(e)}")
            raise

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        try:
            stmt = select(User).where(User.id == user_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {str(e)}")
            raise

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        try:
            stmt = select(User).where(User.username == username)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to get user by username {username}: {str(e)}")
            raise

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        try:
            stmt = select(User).where(User.email == email)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {str(e)}")
            raise

    async def get_user_by_github_id(self, github_id: int) -> Optional[User]:
        """Get user by GitHub ID."""
        try:
            stmt = select(User).where(User.github_id == github_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"Failed to get user by GitHub ID {github_id}: {str(e)}")
            raise

    async def create_or_update_github_user(self, github_data: Dict[str, Any]) -> User:
        """Create or update user from GitHub OAuth data."""
        try:
            github_id = github_data.get("github_id")
            github_username = github_data.get("github_username")
            email = github_data.get("email")

            # Try to find existing user by GitHub ID first
            existing_user = None
            if github_id:
                existing_user = await self.get_user_by_github_id(github_id)

            # If not found by GitHub ID, try by email
            if not existing_user and email:
                existing_user = await self.get_user_by_email(email)

            # If not found by email, try by username
            if not existing_user and github_username:
                existing_user = await self.get_user_by_username(github_username)

            if existing_user:
                # Update existing user with GitHub data
                for key, value in github_data.items():
                    if hasattr(existing_user, key) and value is not None:
                        setattr(existing_user, key, value)

                existing_user.last_login = get_utc_timestamp()
                await self.session.commit()
                await self.session.refresh(existing_user)

                logger.info(f"Updated user {existing_user.username} with GitHub data")
                return existing_user

            else:
                # Create new user
                user_data = {
                    "username": github_data.get("github_username") or github_data.get("username"),
                    "email": github_data.get("email"),
                    "name": github_data.get("name"),
                    "github_id": github_data.get("github_id"),
                    "github_username": github_data.get("github_username"),
                    "avatar_url": github_data.get("avatar_url"),
                    "is_active": True,
                    "last_login": get_utc_timestamp()
                }

                return await self.create_user(user_data)

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create/update GitHub user: {str(e)}")
            raise

    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> Optional[User]:
        """Update user information."""
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                return None

            for key, value in update_data.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            await self.session.commit()
            await self.session.refresh(user)

            logger.info(f"Updated user {user.username}")
            return user

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update user {user_id}: {str(e)}")
            raise

    async def update_last_login(self, user_id: str) -> bool:
        """Update user's last login timestamp."""
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                return False

            user.last_login = get_utc_timestamp()
            await self.session.commit()

            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update last login for user {user_id}: {str(e)}")
            raise

    async def update_user_activity(self, user_id: str) -> bool:
        """Update user's API activity."""
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                return False

            user.api_calls_count += 1
            user.last_api_call = get_utc_timestamp()
            await self.session.commit()

            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update user activity for {user_id}: {str(e)}")
            raise

    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account."""
        try:
            user = await self.get_user_by_id(user_id)
            if not user:
                return False

            user.is_active = False
            await self.session.commit()

            logger.info(f"Deactivated user {user.username}")
            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to deactivate user {user_id}: {str(e)}")
            raise

    async def list_users(
        self,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True
    ) -> List[User]:
        """List users with pagination."""
        try:
            stmt = select(User)

            if active_only:
                stmt = stmt.where(User.is_active == True)

            stmt = stmt.order_by(desc(User.created_at)).limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to list users: {str(e)}")
            raise

    async def search_users(self, query: str, limit: int = 50) -> List[User]:
        """Search users by username, email, or name."""
        try:
            search_term = f"%{query}%"
            stmt = select(User).where(
                or_(
                    User.username.ilike(search_term),
                    User.email.ilike(search_term),
                    User.name.ilike(search_term)
                )
            ).where(User.is_active == True).limit(limit)

            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to search users: {str(e)}")
            raise

    async def get_user_statistics(self) -> Dict[str, Any]:
        """Get user statistics."""
        try:
            # Total users
            total_stmt = select(func.count(User.id))
            total_result = await self.session.execute(total_stmt)
            total_users = total_result.scalar()

            # Active users
            active_stmt = select(func.count(User.id)).where(User.is_active == True)
            active_result = await self.session.execute(active_stmt)
            active_users = active_result.scalar()

            # Users with GitHub integration
            github_stmt = select(func.count(User.id)).where(User.github_id.isnot(None))
            github_result = await self.session.execute(github_stmt)
            github_users = github_result.scalar()

            # Recent logins (last 7 days)
            recent_date = get_utc_timestamp() - timedelta(days=7)
            recent_stmt = select(func.count(User.id)).where(
                and_(
                    User.last_login >= recent_date,
                    User.is_active == True
                )
            )
            recent_result = await self.session.execute(recent_stmt)
            recent_logins = recent_result.scalar()

            return {
                "total_users": total_users,
                "active_users": active_users,
                "github_users": github_users,
                "recent_logins": recent_logins,
                "registration_rate": active_users / max(total_users, 1) * 100
            }

        except Exception as e:
            logger.error(f"Failed to get user statistics: {str(e)}")
            raise

    # API Key management

    async def create_api_key(
        self,
        user_id: str,
        name: str,
        scopes: List[str],
        expires_at: Optional[datetime] = None
    ) -> ApiKey:
        """Create an API key for a user."""
        try:
            from utils.crypto import generate_api_key, hash_password

            # Generate API key
            raw_key = generate_api_key()
            key_hash = hash_password(raw_key)

            api_key = ApiKey(
                user_id=user_id,
                name=name,
                key_hash=key_hash,
                scopes=scopes,
                expires_at=expires_at
            )

            self.session.add(api_key)
            await self.session.commit()
            await self.session.refresh(api_key)

            logger.info(f"Created API key '{name}' for user {user_id}")

            # Return the raw key only once (it won't be stored)
            api_key.raw_key = raw_key
            return api_key

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create API key: {str(e)}")
            raise

    async def get_user_api_keys(self, user_id: str) -> List[ApiKey]:
        """Get all API keys for a user."""
        try:
            stmt = select(ApiKey).where(ApiKey.user_id == user_id)
            result = await self.session.execute(stmt)
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Failed to get API keys for user {user_id}: {str(e)}")
            raise

    async def validate_api_key(self, raw_key: str) -> Optional[User]:
        """Validate API key and return associated user."""
        try:
            from utils.crypto import verify_password

            # Hash the provided key to compare
            stmt = select(ApiKey).where(
                and_(
                    ApiKey.is_active == True,
                    or_(
                        ApiKey.expires_at.is_(None),
                        ApiKey.expires_at > get_utc_timestamp()
                    )
                )
            )

            result = await self.session.execute(stmt)
            api_keys = result.scalars().all()

            # Check each active key
            for api_key in api_keys:
                if verify_password(raw_key, api_key.key_hash):
                    # Update usage
                    api_key.last_used = get_utc_timestamp()
                    api_key.usage_count += 1
                    await self.session.commit()

                    # Get and return user
                    user = await self.get_user_by_id(api_key.user_id)
                    return user

            return None

        except Exception as e:
            logger.error(f"Failed to validate API key: {str(e)}")
            raise

    async def revoke_api_key(self, api_key_id: str, user_id: str) -> bool:
        """Revoke an API key."""
        try:
            stmt = select(ApiKey).where(
                and_(
                    ApiKey.id == api_key_id,
                    ApiKey.user_id == user_id
                )
            )

            result = await self.session.execute(stmt)
            api_key = result.scalar_one_or_none()

            if not api_key:
                return False

            api_key.is_active = False
            await self.session.commit()

            logger.info(f"Revoked API key {api_key_id} for user {user_id}")
            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to revoke API key {api_key_id}: {str(e)}")
            raise