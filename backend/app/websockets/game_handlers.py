# backend/app/websockets/game_handlers.py
import socketio
import uuid
import random  # Make sure random is imported if shuffle is used
from supabase import Client

# Ensure necessary types are imported
from typing import Dict, Any, List, Optional

# Core/DB/Security Imports
from app.core.db import get_supabase_client
from app.core.security import verify_supabase_jwt  # Import JWT verification

# CRUD Imports
from app.crud import games as crud_games
from app.crud import lobbies as crud_lobbies

# Service/Logic Imports
# Import logic classes
from app.services.game_logic import GameSession, GamePhase, GameMode

# WebSocket Management Imports
from app.websockets import game_manager  # Import the in-memory manager

print("GAME_HANDLERS: Initializing Socket.IO AsyncServer...")
# This Socket.IO instance will be imported and used in main.py
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)
print("GAME_HANDLERS: Socket.IO AsyncServer instance created.")


# --- Authentication Helper Functions ---

async def _is_authenticated(sid) -> bool:
    """Checks if the current SID has an authenticated session."""
    async with sio.session(sid) as session:
        return session.get('authenticated', False)


async def _get_user_id(sid) -> Optional[uuid.UUID]:
    """Gets the user ID from the SID's session."""
    async with sio.session(sid) as session:
        user_id_str = session.get('user_id')
        try:
            return uuid.UUID(user_id_str) if user_id_str else None
        except ValueError:
            print(
                f"Error: Invalid UUID format for user_id '{user_id_str}' in session for SID {sid}")
            return None

# --- Socket.IO Event Handlers ---


@sio.event
async def connect(sid, environ, auth):
    """
    Handles new client connections and authenticates using JWT from auth dict.
    """
    print(f"GAME_HANDLERS: Connect attempt from {sid} with auth: {auth}")

    # --- Re-enabled Authentication Check ---
    if not auth or 'token' not in auth:
        print(f"GAME_HANDLERS: Connection rejected (no token): {sid}")
        # Disconnect the client if no token is provided
        raise socketio.exceptions.ConnectionRefusedError(
            'Authentication token required')

    token = auth['token']
    payload = await verify_supabase_jwt(token)  # Verify the token

    if not payload or 'sub' not in payload:
        print(f"GAME_HANDLERS: Connection rejected (invalid token): {sid}")
        raise socketio.exceptions.ConnectionRefusedError(
            'Invalid authentication token')
    # ------------------------------------

    # Extract user ID from 'sub' claim (already validated as present)
    user_id = payload['sub']
    print(f"GAME_HANDLERS: Client authenticated: {sid}, User ID: {user_id}")

    # Store user_id in the Socket.IO session for this client
    async with sio.session(sid) as session:
        # Store as string, convert when retrieving if needed
        session['user_id'] = user_id
        session['authenticated'] = True

    # Optional: Emit success message back to the connected client
    # await sio.emit('connection_success', {'user_id': user_id}, to=sid)


@sio.event
async def disconnect(sid):
    """Handles client disconnections and performs necessary cleanup."""
    # Fetch user_id BEFORE removing SID association if needed for logging/cleanup
    async with sio.session(sid) as session:
        user_id = session.get('user_id', 'Unknown user (session cleared)')
    print(f"GAME_HANDLERS: Client disconnected: {sid}, User: {user_id}")
    # Remove SID association from any active game this SID might have been in
    game_manager.remove_player_sid(sid)
    # Add any other game-specific cleanup logic needed when a user disconnects


@sio.event
async def join_game(sid, data: Dict[str, Any]):
    """Handles a client request to join a specific game's WebSocket room after connecting."""
    print(f"Received join_game request from {sid}: {data}")
    if not await _is_authenticated(sid):
        await sio.emit('error', {'message': 'Authentication required.'}, to=sid)
        return

    user_id = await _get_user_id(sid)  # Already returns UUID or None
    game_id_str = data.get('game_id')

    if not game_id_str or not user_id:
        # Check if user_id failed conversion or wasn't in session
        detail = 'Missing game_id.' if not game_id_str else 'Authentication session error.'
        await sio.emit('error', {'message': detail}, to=sid)
        return

    try:
        game_id = uuid.UUID(game_id_str)
    except ValueError:
        await sio.emit('error', {'message': 'Invalid game_id format.'}, to=sid)
        return

    # Check if user is actually part of this game in the DB
    db: Client = await get_supabase_client()  # Get DB client instance
    game_players: Optional[List[uuid.UUID]] = await crud_games.get_game_players(db, game_id)

    if game_players is None:
        await sio.emit('error', {'message': f'Game {game_id} not found.'}, to=sid)
        return
    if user_id not in game_players:
        await sio.emit('error', {'message': f'You are not a player in game {game_id}.'}, to=sid)
        return

    # Add user to the Socket.IO room for this game
    await sio.enter_room(sid, str(game_id))
    print(f"Added {sid} (User: {user_id}) to room {game_id}")

    # Load game session into memory if not already there
    game_session = game_manager.get_game_session(game_id)
    if not game_session:
        print(f"Game {game_id} not in memory, loading from DB...")
        game_state_json = await crud_games.get_game_state_json(db, game_id)
        if game_state_json:
            try:
                game_session = GameSession.deserialize_state(game_state_json)
                game_manager.add_game_session(game_session)
            except Exception as e:
                print(f"ERROR deserializing game state for {game_id}: {e}")
                await sio.emit('error', {'message': f'Error loading game state for {game_id}.'}, to=sid)
                await sio.leave_room(sid, str(game_id))
                return
        else:
            await sio.emit('error', {'message': f'Could not load game state for {game_id} (DB fetch failed).'}, to=sid)
            # Leave room if game state fails
            await sio.leave_room(sid, str(game_id))
            return

    # Associate SID with Player ID in the game session object
    game_manager.associate_player_sid(game_id, user_id, sid)

    # Emit the current game state TO THE JOINING USER ONLY
    # Add filtering later to hide secret info based on role/state
    # Ensure serialize_state() works correctly
    try:
        state_to_send = game_session.serialize_state()
        # TODO: Filter state_to_send based on user_id/role before emitting
        await sio.emit('game_state', state_to_send, to=sid)
        print(f"Sent current game state of {game_id} to {sid}")
    except Exception as e:
        print(
            f"ERROR serializing game state for {game_id} to send to {sid}: {e}")
        await sio.emit('error', {'message': f'Error preparing game state.'}, to=sid)


@sio.event
async def start_game(sid, data: Dict[str, Any]):
    """Handles request from lobby creator to start the game."""
    print(f"Received start_game request from {sid}: {data}")
    if not await _is_authenticated(sid):
        await sio.emit('error', {'message': 'Authentication required.'}, to=sid)
        return

    user_id = await _get_user_id(sid)
    lobby_id_str = data.get('lobby_id')
    if not lobby_id_str or not user_id:
        detail = 'Missing lobby_id.' if not lobby_id_str else 'Authentication session error.'
        await sio.emit('error', {'message': detail}, to=sid)
        return

    try:
        lobby_id = uuid.UUID(lobby_id_str)
    except ValueError:
        await sio.emit('error', {'message': 'Invalid lobby_id format.'}, to=sid)
        return

    db: Client = await get_supabase_client()

    # 1. Fetch lobby details & verify creator and player count
    lobby = await crud_lobbies.get_lobby(db, lobby_id)
    if not lobby:
        await sio.emit('error', {'message': f'Lobby {lobby_id} not found.'}, to=sid)
        return
    # Compare UUIDs correctly
    if lobby.creator_id != user_id:
        await sio.emit('error', {'message': 'Only the lobby creator can start the game.'}, to=sid)
        return
    if lobby.status != 'waiting':
        await sio.emit('error', {'message': f'Lobby is not in a state to be started (Status: {lobby.status}).'}, to=sid)
        return
    player_count = len(lobby.current_players)
    # Use strict player count check from GameSession init if available or define here
    if not (5 <= player_count <= 15):
        await sio.emit('error', {'message': f'Invalid player count ({player_count}) to start the game.'}, to=sid)
        return

    # 2. Update lobby status
    await crud_lobbies.update_lobby_status_crud(db, lobby_id, 'starting')

    # 3. Create GameSession instance
    game_id = uuid.uuid4()
    player_ids_in_order = list(lobby.current_players)
    random.shuffle(player_ids_in_order)
    try:
        game_session = GameSession(
            game_id=game_id, player_ids=player_ids_in_order, mode=lobby.game_mode)
    except ValueError as e:
        await sio.emit('error', {'message': f'Failed to initialize game: {e}'}, to=sid)
        # Revert status
        await crud_lobbies.update_lobby_status_crud(db, lobby_id, 'waiting')
        return

    # 4. Initialize Game Logic (Roles, Deck)
    try:
        game_session.assign_roles()
        game_session.initialize_deck()
        start_info = game_session.start_game_flow()
    except Exception as e:
        print(f"ERROR during game session setup for {game_id}: {e}")
        await sio.emit('error', {'message': 'Internal server error during game setup.'}, to=sid)
        # Mark as failed
        await crud_lobbies.update_lobby_status_crud(db, lobby_id, 'failed')
        return

    # 5. Persist initial game state to DB
    initial_state_json = game_session.serialize_state()
    created_in_db = await crud_games.create_game(
        db,
        game_id=game_id,
        player_ids=game_session.players,
        initial_state_json=initial_state_json,
        mode=game_session.mode,
        lobby_id=lobby_id
    )
    if not created_in_db:
        await sio.emit('error', {'message': 'Failed to save initial game state to database.'}, to=sid)
        await crud_lobbies.update_lobby_status_crud(db, lobby_id, 'failed')
        return

    # 6. Add session to in-memory manager
    game_manager.add_game_session(game_session)
    print(f"Game {game_id} added to in-memory manager.")

    # 7. Associate SIDs (players should connect and join the game room after finding out game started)
    # We need players to connect via WebSocket and call 'join_game' for the new game_id
    # For now, we assume they *might* be connected from the lobby phase (less ideal)
    # or will connect shortly after receiving the game start signal.
    # Let's skip trying to find SIDs here and rely on join_game to associate them.

    # 8. Emit events to players
    print(f"Starting game {game_id}. Notifying players...")
    full_game_state_for_client = game_session.serialize_state()  # Get latest state

    # Instead of finding SIDs, emit a general 'game_ready' or 'lobby_started_game'
    # event perhaps to the *lobby* room if players were in one, or rely on
    # clients polling the lobby status via REST and then connecting/joining game.
    # --- Let's assume for now clients will get the game_id and call join_game ---
    # --- The join_game handler will send them the state and role ---
    # --- We just need a public event to signal the game started and who is up ---

    # Emit the first public game event (e.g., who is president)
    if start_info and start_info['event'] == 'election_started':
        # We need a way to broadcast this to players who will join the game room.
        # Option A: Send it later when they join.
        # Option B: Send it to the lobby room (if using WS rooms for lobbies).
        # Option C: Rely on client fetching state after seeing lobby status change.

        # Let's postpone the 'election_started' emit until players actually join the game room via join_game
        print(
            f"Game {game_id} ready. Initial state saved. Waiting for players to join WS room.")
        # Store the initial event data to send upon join?
        # game_session.initial_event = start_info # Add this to GameSession if needed
    else:
        print(
            f"ERROR: start_game_flow did not return expected election_started event for game {game_id}")

    # 9. Update lobby status to 'active' (game has started)
    await crud_lobbies.update_lobby_status_crud(db, lobby_id, 'active')
    print(f"Lobby {lobby_id} status updated to active.")


# --- Add more game action handlers below ---
# Example:
# @sio.event
# async def nominate_chancellor(sid, data):
#     if not await _is_authenticated(sid): return await sio.emit('error', ...)
#     user_id = await _get_user_id(sid)
#     game_id = uuid.UUID(data.get('game_id'))
#     chancellor_id = uuid.UUID(data.get('chancellor_id'))
#     game_session = game_manager.get_game_session(game_id)
#     if game_session and game_session.state == GamePhase.NOMINATION and game_session.president_id == user_id:
#         # Call game_session method
#         result = game_session.nominate_chancellor(user_id, chancellor_id)
#         # Persist state change
#         # await crud_games.update_game_state(...)
#         # Emit results/next step to room
#         # await sio.emit('chancellor_nominated', {...}, room=str(game_id))
#         # await sio.emit('request_vote', {...}, room=str(game_id))
#     else:
#         # Emit error (wrong state, not president, game not found)
#         await sio.emit('error', {'message': 'Invalid action or game state.'}, to=sid)
