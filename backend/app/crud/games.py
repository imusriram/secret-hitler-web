# backend/app/crud/games.py
import uuid
from typing import Optional, Dict, Any, List
from supabase import Client
from app.models.lobby import GameMode  # Use the enum

# Assuming Game model is defined similarly in models/game.py if needed
# For now, we work directly with dicts and the GameSession


async def create_game(db: Client, *, game_id: uuid.UUID, player_ids: List[uuid.UUID], initial_state_json: Dict[str, Any], mode: GameMode, lobby_id: Optional[uuid.UUID] = None) -> bool:
    """Creates a new game record in the database."""
    try:
        game_data = {
            "game_id": str(game_id),
            "players": [str(p) for p in player_ids],
            "game_state": initial_state_json,  # Already serialized JSON
            "game_mode": mode.value,  # Store enum value
            "status": "active",  # Or use initial_state_json['status']
            "lobby_id": str(lobby_id) if lobby_id else None
        }
        response = await db.table("games").insert(game_data).execute()
        return len(response.data) > 0
    except Exception as e:
        print(f"Error creating game {game_id} in DB: {e}")
        return False


async def get_game_state_json(db: Client, game_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Fetches the raw game_state JSONB from the database."""
    try:
        response = await db.table("games").select("game_state").eq("game_id", str(game_id)).maybe_single().execute()
        if response.data and 'game_state' in response.data:
            return response.data['game_state']
        return None
    except Exception as e:
        print(f"Error fetching game state for {game_id}: {e}")
        return None


async def update_game_state(db: Client, *, game_id: uuid.UUID, game_state_json: Dict[str, Any], status: str, **kwargs) -> bool:
    """Updates the game_state JSONB and potentially other indexed fields."""
    try:
        update_data = {
            "game_state": game_state_json,
            "status": status,
            "updated_at": "now()"  # Use database's now() function
            # Add other fields to update from kwargs if needed (e.g., policy counts)
            # "liberal_policies_enacted": kwargs.get("liberal_policies", 0),
            # "fascist_policies_enacted": kwargs.get("fascist_policies", 0),
        }
        response = await db.table("games").update(update_data).eq("game_id", str(game_id)).execute()
        # Check if update was successful (e.g., based on count or returned data)
        # Supabase update might not return data by default, check documentation
        # For now, assume success if no exception occurs
        return True
    except Exception as e:
        print(f"Error updating game state for {game_id}: {e}")
        return False


async def get_game_players(db: Client, game_id: uuid.UUID) -> Optional[List[uuid.UUID]]:
    """Fetches the list of player UUIDs for a game."""
    try:
        response = await db.table("games").select("players").eq("game_id", str(game_id)).maybe_single().execute()
        if response.data and 'players' in response.data:
            return [uuid.UUID(p) for p in response.data['players']]
        return None
    except Exception as e:
        print(f"Error fetching players for game {game_id}: {e}")
        return None
