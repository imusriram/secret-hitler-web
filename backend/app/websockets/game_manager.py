# backend/app/websockets/game_manager.py
import uuid
from typing import Dict, Optional
from app.services.game_logic import GameSession

# Simple in-memory storage for active game sessions
# In a larger application, consider more robust solutions (e.g., Redis)
# if scalability or persistence across server restarts is needed without DB load.
active_games: Dict[uuid.UUID, GameSession] = {}


def get_game_session(game_id: uuid.UUID) -> Optional[GameSession]:
    """Retrieves an active game session from memory."""
    return active_games.get(game_id)


def add_game_session(game_session: GameSession):
    """Adds or updates a game session in memory."""
    if not game_session or not game_session.game_id:
        print("Error: Attempted to add invalid game session.")
        return
    active_games[game_session.game_id] = game_session
    print(f"Game session {game_session.game_id} added/updated in memory.")


def remove_game_session(game_id: uuid.UUID):
    """Removes a game session from memory."""
    if game_id in active_games:
        del active_games[game_id]
        print(f"Game session {game_id} removed from memory.")
    else:
        print(
            f"Warning: Attempted to remove non-existent game session {game_id}.")


def associate_player_sid(game_id: uuid.UUID, player_id: uuid.UUID, sid: str):
    """Associates a player's user ID with their WebSocket SID within a game session."""
    session = get_game_session(game_id)
    if session:
        session.player_connections[player_id] = sid
        print(
            f"Associated SID {sid} with Player {player_id} in Game {game_id}")
    else:
        print(
            f"Warning: Could not associate SID {sid}. Game {game_id} not found in memory.")


def remove_player_sid(sid_to_remove: str):
    """Finds which game the SID belongs to and removes the player association."""
    game_id_found = None
    player_id_found = None
    for game_id, session in active_games.items():
        for player_id, sid in session.player_connections.items():
            if sid == sid_to_remove:
                player_id_found = player_id
                game_id_found = game_id
                break
        if game_id_found:
            # Remove the association
            del session.player_connections[player_id_found]
            print(
                f"Removed SID association for Player {player_id_found} in Game {game_id_found}")
            # Optional: Add logic here to notify the game session that a player disconnected
            # if session.status != GamePhase.FINISHED:
            #     session.handle_player_disconnect(player_id_found) # Add this method to GameSession if needed
            break


def get_sid_for_player(game_id: uuid.UUID, player_id: uuid.UUID) -> Optional[str]:
    """Gets the SID for a specific player in a specific game."""
    session = get_game_session(game_id)
    if session:
        return session.player_connections.get(player_id)
    return None
