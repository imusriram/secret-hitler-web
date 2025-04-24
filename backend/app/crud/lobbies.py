# backend/app/crud/lobbies.py
import uuid
from typing import List, Optional
from supabase import Client, AsyncClient  # Use the official Client

from app.models.lobby import LobbyCreate, LobbyInDB, LobbyUpdate


async def create_lobby(db: AsyncClient, *, creator_id: uuid.UUID, settings: LobbyCreate) -> Optional[LobbyInDB]:
    """Creates a new lobby in the database."""
    try:
        lobby_data = settings.model_dump()  # Pydantic v2 uses model_dump()
        # Ensure UUID is string for insert
        lobby_data['creator_id'] = str(creator_id)
        lobby_data['current_players'] = [
            str(creator_id)]  # Creator joins automatically
        lobby_data['status'] = 'waiting'

        # Execute without await - the AsyncClient's execute() method returns a coroutine
        response = await db.table("game_lobbies").insert(lobby_data).execute()

        if response.data:
            # Fetch the created lobby to get all fields including defaults like lobby_id, created_at
            created_lobby_data = response.data[0]
            # Convert player IDs back to UUIDs if necessary for the model
            created_lobby_data['current_players'] = [
                uuid.UUID(p) for p in created_lobby_data.get('current_players', [])]
            return LobbyInDB(**created_lobby_data)
        return None
    except Exception as e:
        print(f"Error creating lobby for user {creator_id}: {e}")
        return None


async def get_lobby(db: AsyncClient, lobby_id: uuid.UUID) -> Optional[LobbyInDB]:
    """Fetches a specific lobby by its ID."""
    try:
        response = await db.table("game_lobbies").select("*").eq("lobby_id", str(lobby_id)).maybe_single().execute()
        
        if response.data:
            lobby_data = response.data
            lobby_data['current_players'] = [
                uuid.UUID(p) for p in lobby_data.get('current_players', [])]
            return LobbyInDB(**lobby_data)
        return None
    except Exception as e:
        print(f"Error fetching lobby {lobby_id}: {e}")
        return None


async def list_available_lobbies(db: AsyncClient) -> List[LobbyInDB]:
    """Lists lobbies that are currently waiting for players."""
    lobbies = []
    try:
        response = await db.table("game_lobbies").select("*").eq("status", "waiting").order("created_at", desc=False).execute()
        if response.data:
            for item in response.data:
                # Convert player IDs back to UUIDs
                item['current_players'] = [
                    uuid.UUID(p) for p in item.get('current_players', [])]
                lobbies.append(LobbyInDB(**item))
        return lobbies
    except Exception as e:
        print(f"Error listing available lobbies: {e}")
        return []  # Return empty list on error


async def update_lobby(db: AsyncClient, lobby_id: uuid.UUID, update_data: LobbyUpdate) -> Optional[LobbyInDB]:
    """Updates a lobby with the provided data."""
    try:
        # Convert UUID list to string list for Supabase if updating players
        update_dict = update_data.model_dump(exclude_unset=True)
        if 'current_players' in update_dict and update_dict['current_players'] is not None:
            update_dict['current_players'] = [
                str(p) for p in update_dict['current_players']]

        response = await db.table("game_lobbies").update(update_dict).eq("lobby_id", str(lobby_id)).execute()

        if response.data:
            # Fetch the updated lobby data
            updated_lobby_data = response.data[0]
            updated_lobby_data['current_players'] = [
                uuid.UUID(p) for p in updated_lobby_data.get('current_players', [])]
            return LobbyInDB(**updated_lobby_data)
        return None  # Or raise error if update should have returned data
    except Exception as e:
        print(f"Error updating lobby {lobby_id}: {e}")
        return None

# Specific update functions might be cleaner


async def add_player_to_lobby_crud(db: AsyncClient, lobby_id: uuid.UUID, player_id: uuid.UUID) -> bool:
    """Adds a player to the lobby's player list using Supabase append."""
    try:
        # Note: Supabase rpc or direct array append might be needed for atomicity
        # This simple fetch/update can have race conditions.
        lobby = await get_lobby(db, lobby_id)
        if not lobby:
            return False
        if player_id in lobby.current_players:
            return True  # Already joined
        if len(lobby.current_players) >= lobby.max_players:
            return False  # Lobby full

        new_player_list = lobby.current_players + [player_id]
        updated = await update_lobby(db, lobby_id, LobbyUpdate(current_players=new_player_list))
        return updated is not None

    except Exception as e:
        print(f"Error adding player {player_id} to lobby {lobby_id}: {e}")
        return False


async def remove_player_from_lobby_crud(db: AsyncClient, lobby_id: uuid.UUID, player_id: uuid.UUID) -> bool:
    """Removes a player from the lobby's player list."""
    try:
        lobby = await get_lobby(db, lobby_id)
        if not lobby or player_id not in lobby.current_players:
            return False  # Lobby not found or player not in it

        new_player_list = [p for p in lobby.current_players if p != player_id]
        updated = await update_lobby(db, lobby_id, LobbyUpdate(current_players=new_player_list))
        return updated is not None

    except Exception as e:
        print(f"Error removing player {player_id} from lobby {lobby_id}: {e}")
        return False


async def update_lobby_status_crud(db: AsyncClient, lobby_id: uuid.UUID, status: str) -> bool:
    """Updates only the status of a lobby."""
    updated = await update_lobby(db, lobby_id, LobbyUpdate(status=status))
    return updated is not None
