"""Authentication handlers for the Git Review Assistant API."""

from fastapi import APIRouter, HTTPException, Depends, status, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import time

from config.logging import get_logger, security_logger
from config.settings import settings
from models.api import AuthToken, UserInfo, APIResponse, APIStatus, APIError, ErrorCode
from utils.crypto import verify_jwt_token, create_jwt_token, hash_password, verify_password
from database.connection import get_db_session
from database.repositories.user_repository import UserRepository

logger = get_logger(__name__)
auth_router = APIRouter()

# Security scheme
security = HTTPBearer(auto_error=False)


class AuthenticationError(Exception):
    """Custom authentication error."""
    pass


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db_session = Depends(get_db_session)
) -> Optional[UserInfo]:
    """
    Get current authenticated user from JWT token.

    Returns None if no valid token is provided (for optional auth).
    Raises HTTPException for invalid tokens.
    """
    if not credentials:
        return None

    try:
        # Verify JWT token
        payload = verify_jwt_token(credentials.credentials)
        user_id = payload.get("sub")

        if not user_id:
            raise AuthenticationError("Invalid token payload")

        # Get user from database
        user_repo = UserRepository(db_session)
        user = await user_repo.get_user_by_id(user_id)

        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        # Update last API call
        await user_repo.update_user_activity(user_id)

        return UserInfo(
            id=str(user.id),
            username=user.username,
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            github_id=user.github_id,
            created_at=user.created_at,
            last_login=user.last_login,
            is_active=user.is_active
        )

    except AuthenticationError as e:
        security_logger.authentication_attempt("unknown", False, "jwt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def require_auth(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """Require authentication - raises 401 if user is not authenticated."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return current_user


async def require_admin(current_user: UserInfo = Depends(require_auth)) -> UserInfo:
    """Require admin privileges."""
    # Check if user is admin (would need to add is_admin field to UserInfo)
    # For now, we'll check based on username or email
    admin_users = ["admin", "root"]  # Placeholder - removed ALLOWED_ORIGINS as it's not users

    if current_user.username not in admin_users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    return current_user


@auth_router.post("/github/callback")
async def github_oauth_callback(
    code: str,
    state: Optional[str] = None,
    db_session = Depends(get_db_session)
):
    """
    Handle GitHub OAuth callback.

    This would normally exchange the code for an access token
    and create/update user records.
    """
    try:
        # For demo purposes, we'll create a mock implementation
        # In a real implementation, you would:
        # 1. Exchange code for GitHub access token
        # 2. Get user info from GitHub API
        # 3. Create/update user in database
        # 4. Generate JWT token for our app

        logger.info("GitHub OAuth callback received", code=code[:10] + "...")

        # Mock user creation (replace with real GitHub API integration)
        user_repo = UserRepository(db_session)

        # For development, create a test user
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "name": "Test User",
            "github_id": 12345,
            "github_username": "testuser",
            "avatar_url": "https://github.com/identicons/testuser.png"
        }

        user = await user_repo.create_or_update_github_user(user_data)

        # Generate JWT token
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "github_id": user.github_id,
            "iat": int(time.time())
        }

        access_token = create_jwt_token(token_data, expires_delta=86400)  # 24 hours

        security_logger.authentication_attempt(user.username, True, "github")

        return AuthToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=86400,
            expires_at=time.time() + 86400
        )

    except Exception as e:
        logger.error(f"GitHub OAuth callback failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth authentication failed"
        )


@auth_router.post("/token", response_model=AuthToken)
async def create_access_token(
    username: str,
    password: str,
    db_session = Depends(get_db_session)
):
    """
    Create access token with username/password authentication.

    This is mainly for development/testing. Production should use GitHub OAuth.
    """
    try:
        user_repo = UserRepository(db_session)

        # Get user by username
        user = await user_repo.get_user_by_username(username)

        if not user or not user.is_active:
            security_logger.authentication_attempt(username, False, "password")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )

        # For demo purposes, accept any password for the test user
        # In production, you would verify hashed passwords
        if username != "testuser":
            security_logger.authentication_attempt(username, False, "password")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )

        # Generate JWT token
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "github_id": user.github_id,
            "iat": int(time.time())
        }

        access_token = create_jwt_token(token_data, expires_delta=86400)

        # Update last login
        await user_repo.update_last_login(str(user.id))

        security_logger.authentication_attempt(username, True, "password")

        return AuthToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=86400,
            expires_at=time.time() + 86400
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token creation failed"
        )


@auth_router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: UserInfo = Depends(require_auth)):
    """Get current user information."""
    return current_user


@auth_router.post("/logout")
async def logout(current_user: UserInfo = Depends(require_auth)):
    """
    Logout current user.

    Since we're using stateless JWT tokens, this just returns success.
    In a production system, you might want to blacklist the token.
    """
    logger.info(f"User {current_user.username} logged out")

    return APIResponse(
        status=APIStatus.SUCCESS,
        message="Logged out successfully"
    )


@auth_router.post("/refresh", response_model=AuthToken)
async def refresh_token(current_user: UserInfo = Depends(require_auth)):
    """Refresh access token."""
    try:
        # Generate new JWT token
        token_data = {
            "sub": current_user.id,
            "username": current_user.username,
            "github_id": current_user.github_id,
            "iat": int(time.time())
        }

        access_token = create_jwt_token(token_data, expires_delta=86400)

        return AuthToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=86400,
            expires_at=time.time() + 86400
        )

    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@auth_router.get("/github/login")
async def github_login_url():
    """Get GitHub OAuth login URL."""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth not configured"
        )

    # Generate OAuth URL
    github_oauth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&scope=user:email,read:user"
        f"&state=random_state_string"  # Should be cryptographically random
    )

    return {
        "login_url": github_oauth_url,
        "instructions": "Visit this URL to authenticate with GitHub"
    }


@auth_router.get("/status")
async def auth_status(current_user: Optional[UserInfo] = Depends(get_current_user)):
    """Get authentication status."""
    if current_user:
        return {
            "authenticated": True,
            "user": current_user,
            "auth_method": "jwt"
        }
    else:
        return {
            "authenticated": False,
            "user": None,
            "auth_method": None
        }


# Development/Testing endpoints

@auth_router.post("/dev/create-user")
async def create_dev_user(
    username: str,
    email: str,
    name: str = None,
    db_session = Depends(get_db_session)
):
    """Create a development user (only available in debug mode)."""
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        user_repo = UserRepository(db_session)

        user_data = {
            "username": username,
            "email": email,
            "name": name or username,
            "github_id": None,
            "github_username": None,
            "avatar_url": None
        }

        user = await user_repo.create_user(user_data)

        return {
            "message": f"User {username} created successfully",
            "user_id": str(user.id)
        }

    except Exception as e:
        logger.error(f"Failed to create dev user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Rate limiting and security checks

async def check_rate_limit(
    user_id: str,
    endpoint: str,
    limit: int = 100,
    window: int = 3600  # 1 hour
) -> bool:
    """
    Check if user has exceeded rate limit.

    This is a simple implementation. In production, you'd use Redis
    or a proper rate limiting service.
    """
    # For now, always return True (no rate limiting)
    # In production, implement proper rate limiting
    return True


async def log_security_event(
    event_type: str,
    user_id: Optional[str],
    details: Dict[str, Any],
    success: bool = True
):
    """Log security-related events for monitoring."""
    security_logger.logger.info(
        f"Security event: {event_type}",
        user_id=user_id,
        success=success,
        details=details
    )


# Error handlers specific to auth

# Exception handlers moved to main.py since APIRouter doesn't support them
# async def auth_exception_handler(request, exc):
#     """Handle authentication errors."""
#     return JSONResponse(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         content={
#             "error": {
#                 "code": ErrorCode.AUTHENTICATION_ERROR,
#                 "message": str(exc),
#                 "timestamp": time.time()
#             }
#         }
#     )