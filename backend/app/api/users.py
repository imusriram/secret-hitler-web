# backend/app/api/users.py
from fastapi import APIRouter, Depends, HTTPException
import uuid

from app.models.user import UserPublic, UserInDB  # Import the public user model
from app.api import deps  # Import the dependencies module

router = APIRouter()


@router.get("/me", response_model=UserPublic)
async def read_users_me(
    current_user: UserInDB = Depends(
        deps.get_current_user_profile)  # Use the dependency
):
    """
    Get current authenticated user's profile.
    """
    # The dependency already fetches and validates the user
    # We return UserPublic to potentially filter fields if needed
    return current_user

# Optional: Endpoint to get any user's public profile by ID (no auth needed)
from app.core.db import get_supabase_client
from app.crud.users import get_profile_by_user_id
from supabase import AsyncClient

@router.get("/{user_id}", response_model=UserPublic)
async def read_user_profile(
    user_id: uuid.UUID,
    db: AsyncClient = Depends(get_supabase_client)
):
    """Get a user's public profile by ID."""
    user = await get_profile_by_user_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
