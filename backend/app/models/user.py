from pydantic import BaseModel, ConfigDict, Field, EmailStr
import uuid
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True
    )
    
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserInDB(UserBase):
    user_id: uuid.UUID
    created_at: datetime
    hashed_password: str
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        from_attributes=True
    )

class UserPublic(UserBase):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True
    )
    
    user_id: uuid.UUID
    created_at: datetime
