from pydantic import BaseModel, ConfigDict, Field
from enum import Enum
from typing import List, Optional
from datetime import datetime
import uuid

class GameMode(str, Enum):
    NORMAL = "Normal"
    XL = "XL"

# Base Lobby model
class LobbyBase(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        use_enum_values=True
    )
    
    max_players: int = Field(default=10, ge=5, le=15)
    game_mode: GameMode = Field(default=GameMode.NORMAL)

# Model for creating a new lobby
class LobbyCreate(LobbyBase):
    pass

# Model for updating an existing lobby
class LobbyUpdate(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        use_enum_values=True
    )
    
    max_players: Optional[int] = Field(default=None, ge=5, le=15)
    game_mode: Optional[GameMode] = None
    current_players: Optional[List[uuid.UUID]] = None
    status: Optional[str] = None

# Model for lobby stored in DB
class LobbyInDB(LobbyBase):
    lobby_id: uuid.UUID
    creator_id: uuid.UUID
    current_players: List[uuid.UUID]
    status: str
    created_at: datetime
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        use_enum_values=True,
        from_attributes=True
    )

# Public lobby model (returned to clients)
class LobbyPublic(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
        use_enum_values=True
    )
    
    lobby_id: uuid.UUID
    creator_id: uuid.UUID
    current_player_count: int
    max_players: int
    game_mode: GameMode
    status: str
    created_at: datetime
