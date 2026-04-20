# Route handlers for POST /register, /login, and /refresh token endpoints.
"""
app/api/auth.py

Auth routes — register, login, refresh.
Route handlers only. All business logic lives in AuthService / auth_service.py.
All errors return the standard JSON error envelope.
"""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.data.models import User
from app.services.auth_service import (
    InvalidTokenError,
    TokenExpiredError,
    create_token_pair,
    create_access_token,
    hash_password,
    verify_password,
    verify_refresh_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _error(code: str, message: str, status_code: int) -> HTTPException:
    """
    Build a structured error response matching the standard error envelope:
    { "error": { "code": "...", "message": "...", "status": ... } }
    """
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message, "status": status_code}},
    )


# ── Request / Response schemas ────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new user account.
    - email must be valid and unique
    - password minimum 8 characters (validated by Pydantic)
    """
    # Check for Pydantic validation errors surfaced as 400
    # (EmailStr and password_min_length validator handle format)

    # Uniqueness check
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise _error(
            code="EMAIL_EXISTS",
            message="This email address is already registered.",
            status_code=status.HTTP_409_CONFLICT,
        )

    new_user = User(
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return RegisterResponse(
        user_id=str(new_user.id),
        email=new_user.email,
        message="Account created successfully.",
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login and receive JWT tokens",
)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate with email + password.
    Returns access_token (15 min) and refresh_token (7 days).
    Deliberately vague error message — never reveal whether email or password is wrong.
    """
    user = db.query(User).filter(User.email == body.email).first()

    # Constant-time path: always call verify_password even if user not found
    # to prevent timing-based user enumeration
    dummy_hash = "$2b$12$invalidhashpadding000000000000000000000000000000000000000"
    stored_hash = user.password_hash if user else dummy_hash

    password_valid = verify_password(body.password, stored_hash)

    if not user or not password_valid:
        raise _error(
            code="INVALID_CREDENTIALS",
            message="Invalid email or password.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    tokens = create_token_pair(str(user.id))
    return LoginResponse(**tokens)


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange a refresh token for a new access token",
)
def refresh(body: RefreshRequest):
    """
    Use a valid refresh token (7-day TTL) to obtain a new access token.
    Does not require Authorization header — the refresh token IS the credential.
    """
    try:
        user_id = verify_refresh_token(body.refresh_token)
    except TokenExpiredError:
        raise _error(
            code="TOKEN_EXPIRED",
            message="Refresh token has expired. Please log in again.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    except InvalidTokenError:
        raise _error(
            code="INVALID_TOKEN",
            message="Refresh token is invalid or has been tampered with.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    new_access_token = create_access_token(user_id)
    return RefreshResponse(
        access_token=new_access_token,
        expires_in=15 * 60,  # 900 seconds
    )


# ── Reusable auth dependency ──────────────────────────────────────────────────
# Import this in other route files to protect endpoints with JWT.
#
# Usage in a protected route:
#   @router.post("/upload")
#   def upload(user_id: str = Depends(get_current_user_id), ...):
#       ...

def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    """
    FastAPI dependency — extracts and validates the Bearer token from the
    Authorization header. Returns the user_id on success.
    Raises 401 on missing, expired, or invalid token.
    Inject this into any protected route via: Depends(get_current_user_id)
    """
    from app.services.auth_service import verify_access_token  # local import avoids circular

    if credentials is None:
        raise _error(
            code="INVALID_TOKEN",
            message="Authentication required. Include: Authorization: Bearer <token>",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        user_id = verify_access_token(credentials.credentials)
    except TokenExpiredError:
        raise _error(
            code="TOKEN_EXPIRED",
            message="Session expired. Please log in again.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    except InvalidTokenError:
        raise _error(
            code="INVALID_TOKEN",
            message="Authentication required.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    return user_id