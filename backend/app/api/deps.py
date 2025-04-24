# backend/app/api/deps.py
import uuid
from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from supabase import AsyncClient

from app.core.security import verify_supabase_jwt
from app.core.db import get_supabase_client  # Import Supabase client getter
from app.crud.users import get_profile_by_user_id  # Import CRUD function
from app.models.user import UserInDB  # Import user model

# This scheme doesn't perform validation itself, it just extracts the token
# from the 'Authorization: Bearer <token>' header.
api_key_header_auth = APIKeyHeader(name="Authorization", auto_error=True)


async def get_token_from_header(api_key: str = Security(api_key_header_auth)) -> str:
    """Extracts the token from the 'Authorization: Bearer <token>' header."""
    if not api_key.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Must be 'Bearer <token>'",
        )
    return api_key.split(" ")[1]  # Return only the token part


async def get_current_user_id(token: str = Depends(get_token_from_header)) -> uuid.UUID:
    """
    Dependency to verify token and get user ID.
    Raises HTTPException if token is invalid.
    """
    payload = await verify_supabase_jwt(token)
    if not payload or 'sub' not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = uuid.UUID(payload['sub'])  # Convert 'sub' claim to UUID
        return user_id
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_profile(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncClient = Depends(get_supabase_client)
) -> UserInDB:
    """
    Dependency to get the full profile of the current authenticated user.
    Raises HTTPException if profile not found (should be rare if linked to auth).
    """
    user = await get_profile_by_user_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User profile not found")
    return user
