# JWT creation and validation, bcrypt password hashing, and token refresh logic.
"""
app/services/auth_service.py

Auth service — handles password hashing and JWT token operations.
No database queries live here; DB access is handled by the data layer.
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

# ── Config ────────────────────────────────────────────────────────────────────

SECRET_KEY: str = os.environ["SECRET_KEY"]  # Raises KeyError at startup if missing — intentional
ALGORITHM: str = "HS256"
ACCESS_TOKEN_TTL_MINUTES: int = 15
REFRESH_TOKEN_TTL_DAYS: int = 7
BCRYPT_COST_FACTOR: int = 12

# Token type identifiers embedded in the JWT payload
_TOKEN_TYPE_ACCESS = "access"
_TOKEN_TYPE_REFRESH = "refresh"


# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt with cost factor 12.
    Returns a 60-character bcrypt hash string.
    """
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=BCRYPT_COST_FACTOR)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """
    Verify a plain-text password against a stored bcrypt hash.
    Returns True if the password matches, False otherwise.
    Constant-time comparison — safe against timing attacks.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


# ── JWT creation ──────────────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    """
    Create a signed JWT access token with a 15-minute TTL.
    Payload contains: sub (user_id), type, iat, exp.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": _TOKEN_TYPE_ACCESS,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    """
    Create a signed JWT refresh token with a 7-day TTL.
    Payload contains: sub (user_id), type, iat, exp.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": _TOKEN_TYPE_REFRESH,
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_TTL_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_token_pair(user_id: str) -> dict:
    """
    Convenience function — returns both tokens in one call.
    Used at login time.
    """
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_TTL_MINUTES * 60,  # seconds
    }


# ── JWT validation ────────────────────────────────────────────────────────────

class TokenExpiredError(Exception):
    """Raised when a JWT token has passed its expiry time."""


class InvalidTokenError(Exception):
    """Raised when a JWT token is malformed, tampered, or has wrong type."""


def _decode_token(token: str, expected_type: str) -> dict:
    """
    Internal helper — decode and validate a JWT token.
    Raises TokenExpiredError or InvalidTokenError on failure.
    Returns the full decoded payload on success.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError("Token has expired.")
    except JWTError:
        raise InvalidTokenError("Token is invalid or has been tampered with.")

    if payload.get("type") != expected_type:
        raise InvalidTokenError(
            f"Wrong token type. Expected '{expected_type}', got '{payload.get('type')}'."
        )

    return payload


def verify_access_token(token: str) -> str:
    """
    Validate an access token.
    Returns the user_id (sub) on success.
    Raises TokenExpiredError or InvalidTokenError on failure.
    """
    payload = _decode_token(token, expected_type=_TOKEN_TYPE_ACCESS)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise InvalidTokenError("Token payload missing 'sub' claim.")
    return user_id


def verify_refresh_token(token: str) -> str:
    """
    Validate a refresh token and return a new access token.
    Returns the user_id (sub) on success.
    Raises TokenExpiredError or InvalidTokenError on failure.
    """
    payload = _decode_token(token, expected_type=_TOKEN_TYPE_REFRESH)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise InvalidTokenError("Token payload missing 'sub' claim.")
    return user_id
