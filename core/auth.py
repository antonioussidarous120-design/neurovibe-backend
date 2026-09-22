import logging
import jwt
from fastapi import Request
from core.config import settings, TEST_USER_ID

logger = logging.getLogger(__name__)


def get_user_id(request: Request) -> str:
    """Extract the authenticated Supabase user ID from a Bearer JWT.

    If no valid token is present, falls back to TEST_USER_ID so that the app
    remains functional for unauthenticated/demo users during development.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return TEST_USER_ID

    token = auth[7:].strip()
    if not token:
        return TEST_USER_ID

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},  # Supabase uses 'authenticated' as the audience
        )
        user_id: str | None = payload.get("sub")
        if user_id:
            return user_id
        logger.warning("JWT decoded but 'sub' claim missing")
    except jwt.ExpiredSignatureError:
        logger.debug("JWT expired")
    except jwt.InvalidTokenError as exc:
        logger.debug(f"JWT invalid: {exc}")
    except Exception as exc:
        logger.warning(f"Unexpected JWT decode error: {exc}")

    return TEST_USER_ID
