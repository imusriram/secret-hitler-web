# backend/app/crud/users.py
import uuid
from typing import Optional
from supabase import AsyncClient
from app.models.user import UserInDB
from datetime import datetime


async def get_profile_by_user_id(db: AsyncClient, *, user_id: uuid.UUID) -> Optional[UserInDB]:
    """
    Fetches a user profile from the 'profiles' table.
    
    Note: Direct access to auth.users is restricted, so we rely on the profiles table
    which should contain all necessary user information except sensitive auth data.
    """
    try:
        # Fetch profile data only
        response = await db.table("profiles").select("*").eq("id", str(user_id)).single().execute()
        
        if response.data:
            # Map database fields to model fields
            user_data = response.data
            # Map 'id' to 'user_id'
            user_data['user_id'] = uuid.UUID(user_data.pop('id'))
            
            # Set defaults for required fields if missing
            if 'created_at' not in user_data or user_data['created_at'] is None:
                user_data['created_at'] = datetime.now()
            if 'hashed_password' not in user_data:
                user_data['hashed_password'] = ""  # We don't have access to this
            if 'email' not in user_data or user_data['email'] is None:
                # If email is not in profiles table, we can't access it directly
                user_data['email'] = None
            if 'username' not in user_data or user_data['username'] is None:
                user_data['username'] = f"user_{str(user_id)[:8]}"  # Generate username from ID
                
            return UserInDB(**user_data)
        return None
    except Exception as e:
        print(f"Error fetching profile for user {user_id}: {e}")
        # Consider logging the error properly
        return None
