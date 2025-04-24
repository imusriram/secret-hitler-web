# backend/app/api/lobbies.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import uuid
from supabase import AsyncClient  # Use official AsyncClient

from app.models.lobby import LobbyCreate, LobbyPublic, LobbyInDB  # Import models
from app.crud import lobbies as crud_lobbies  # Import CRUD functions
from app.api import deps  # Import auth dependencies
from app.core.db import get_supabase_client  # Import DB dependency

router = APIRouter()


@router.post("", response_model=LobbyPublic, status_code=status.HTTP_201_CREATED)
async def create_new_lobby(
    *,
    db: AsyncClient = Depends(get_supabase_client),
    lobby_in: LobbyCreate,
    current_user_id: uuid.UUID = Depends(
        deps.get_current_user_id)  # Use ID dependency
):
    """
    Create a new game lobby. The creator automatically joins.
    """
    lobby = await crud_lobbies.create_lobby(db, creator_id=current_user_id, settings=lobby_in)
    if not lobby:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create lobby.",
        )
    # Convert to LobbyPublic for response
    return LobbyPublic(
        lobby_id=lobby.lobby_id,
        creator_id=lobby.creator_id,
        current_player_count=len(lobby.current_players),
        max_players=lobby.max_players,
        game_mode=lobby.game_mode,
        status=lobby.status,
        created_at=lobby.created_at
    )


@router.get("", response_model=List[LobbyPublic])
async def get_available_lobbies(
    db: AsyncClient = Depends(get_supabase_client),
    # Add pagination later if needed (skip: int = 0, limit: int = 100)
):
    """
    Retrieve a list of currently available lobbies ('waiting' status).
    """
    db_lobbies = await crud_lobbies.list_available_lobbies(db)
    public_lobbies = [
        LobbyPublic(
            lobby_id=lobby.lobby_id,
            creator_id=lobby.creator_id,
            current_player_count=len(lobby.current_players),
            max_players=lobby.max_players,
            game_mode=lobby.game_mode,
            status=lobby.status,
            created_at=lobby.created_at
        ) for lobby in db_lobbies
    ]
    return public_lobbies


@router.get("/{lobby_id}", response_model=LobbyPublic)
async def get_specific_lobby(
    lobby_id: uuid.UUID,
    db: AsyncClient = Depends(get_supabase_client),
):
    """
    Get details for a specific lobby.
    """
    lobby = await crud_lobbies.get_lobby(db, lobby_id=lobby_id)
    if not lobby:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found")
    # Convert to LobbyPublic
    return LobbyPublic(
        lobby_id=lobby.lobby_id,
        creator_id=lobby.creator_id,
        current_player_count=len(lobby.current_players),
        max_players=lobby.max_players,
        game_mode=lobby.game_mode,
        status=lobby.status,
        created_at=lobby.created_at
    )


@router.post("/{lobby_id}/join", response_model=LobbyPublic)
async def join_lobby(
    lobby_id: uuid.UUID,
    db: AsyncClient = Depends(get_supabase_client),
    current_user_id: uuid.UUID = Depends(deps.get_current_user_id)
):
    """
    Allows the authenticated user to join a specific lobby.
    """
    # Attempt to add the player using the specific CRUD function
    success = await crud_lobbies.add_player_to_lobby_crud(db, lobby_id=lobby_id, player_id=current_user_id)

    if not success:
        # Fetch lobby to check reason for failure (e.g., full, not found)
        lobby = await crud_lobbies.get_lobby(db, lobby_id=lobby_id)
        if not lobby:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found")
        if len(lobby.current_players) >= lobby.max_players:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Lobby is full")
        # Check if already joined (should be handled by crud)
        if current_user_id in lobby.current_players:
            pass  # Allow idempotency - already joined is not an error
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not join lobby")

    # Fetch the updated lobby state to return
    updated_lobby = await crud_lobbies.get_lobby(db, lobby_id=lobby_id)
    if not updated_lobby:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found after join")  # Should not happen

    return LobbyPublic(
        lobby_id=updated_lobby.lobby_id,
        creator_id=updated_lobby.creator_id,
        current_player_count=len(updated_lobby.current_players),
        max_players=updated_lobby.max_players,
        game_mode=updated_lobby.game_mode,
        status=updated_lobby.status,
        created_at=updated_lobby.created_at
    )


@router.post("/{lobby_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_lobby(
    lobby_id: uuid.UUID,
    db: AsyncClient = Depends(get_supabase_client),
    current_user_id: uuid.UUID = Depends(deps.get_current_user_id)
):
    """
    Allows the authenticated user to leave a specific lobby.
    """
    # Fetch lobby first to check if user is actually in it
    lobby = await crud_lobbies.get_lobby(db, lobby_id=lobby_id)
    if not lobby:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lobby not found")
    if current_user_id not in lobby.current_players:
        # Idempotent: If user isn't in the lobby, act as if leave was successful
        return status.HTTP_204_NO_CONTENT

    # Handle case where creator leaves - should we delete the lobby? For now, just remove.
    # if lobby.creator_id == current_user_id:
        # print(f"Lobby creator {current_user_id} is leaving lobby {lobby_id}")
        # Potentially delete lobby or assign new creator? TBD.

    success = await crud_lobbies.remove_player_from_lobby_crud(db, lobby_id=lobby_id, player_id=current_user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not leave lobby")

    return status.HTTP_204_NO_CONTENT  # Success, no content to return
