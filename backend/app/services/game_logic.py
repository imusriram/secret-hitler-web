# backend/app/services/game_logic.py
import random
import uuid
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timezone
from app.models.lobby import GameMode  # Use the enum defined earlier
from pydantic import BaseModel, ConfigDict, Field

# Define potential game states (adjust as needed)


class GamePhase:
    LOBBY = "lobby"  # Should ideally not be handled by GameSession itself
    STARTING = "starting"
    NOMINATION = "nomination"
    VOTING = "voting"
    LEGISLATIVE_PRESIDENT_DISCARD = "legislative_president_discard"
    LEGISLATIVE_CHANCELLOR_ENACT = "legislative_chancellor_enact"
    EXECUTIVE_ACTION = "executive_action"
    POST_ACTION = "post_action"  # Brief state after action before next round/end
    FINISHED = "finished"


class GameSession:
    def __init__(self, game_id: uuid.UUID, player_ids: List[uuid.UUID], mode: GameMode = GameMode.NORMAL):
        if not (5 <= len(player_ids) <= 15):  # Adjust max players as needed
            raise ValueError(
                f"Invalid number of players: {len(player_ids)}. Must be between 5 and 15.")

        self.game_id: uuid.UUID = game_id
        self.initial_player_ids: List[uuid.UUID] = list(
            player_ids)  # Keep original list if needed
        # Active players, might change on execution
        self.players: List[uuid.UUID] = list(player_ids)
        self.mode: GameMode = mode
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = self.created_at
        self.status: str = GamePhase.STARTING  # Initial status

        # --- Core Game State ---
        self.roles: Dict[uuid.UUID, str] = {}  # Player ID -> Role Name
        self.policies: List[str] = []  # The draw pile
        self.discard_pile: List[str] = []
        self.enacted_policies: Dict[str, int] = {  # Count of enacted policies
            "Liberal": 0,
            "Fascist": 0,
            "Communist": 0,  # XL
            "Anarchist": 0,  # XL
            # Keep track even if not standard win condition?
            "Anti Fascist": 0,  # XL Policy effect
            "Anti Communist": 0  # XL Policy effect
        }
        self.liberal_track_bonuses_used: List[bool] = [
            False] * 5  # Example if needed
        self.fascist_track_bonuses_used: List[bool] = [False] * 6
        self.communist_track_bonuses_used: List[bool] = [False] * 6  # XL

        # --- Round State ---
        self.state: str = GamePhase.STARTING  # Current phase of the game
        # Index in self.players list
        self.president_index: Optional[int] = None
        self.president_id: Optional[uuid.UUID] = None
        self.chancellor_candidate_id: Optional[uuid.UUID] = None
        # Confirmed chancellor for the term
        self.chancellor_id: Optional[uuid.UUID] = None
        # Player ID -> Vote (True=Ja, False=Nein)
        self.votes: Dict[uuid.UUID, bool] = {}
        self.election_tracker: int = 0
        self.last_government: Dict[str, Optional[uuid.UUID]] = {
            "president": None, "chancellor": None}
        # Policies president sees
        self.policies_drawn_for_legislative: List[str] = []
        # Policies chancellor sees
        self.policies_for_chancellor: List[str] = []

        # --- Player Specific State ---
        self.executed_players: List[uuid.UUID] = []
        # Store websocket SIDs associated with player IDs when they connect/join
        # This is NOT part of the persistent state saved to DB, managed by WebSocket layer
        self.player_connections: Dict[uuid.UUID, str] = {}

        # --- Mode Specific Flags ---
        # XL Mode potentially
        self.anarchy_execution_available: bool = True  # If Anarchist power can be used
        self.propaganda_used_this_round: bool = False
        self.vonc_available_this_round: bool = True  # Vote of no confidence

        print(
            f"GameSession {self.game_id} initialized for {len(self.players)} players in {self.mode} mode.")

    # --- State Management Methods ---
    def _touch_updated_at(self):
        """Updates the internal timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def serialize_state(self) -> Dict[str, Any]:
        """Serializes the game state for saving to DB (JSONB)."""
        self._touch_updated_at()
        # Exclude non-persistent data like player_connections
        state = self.__dict__.copy()
        del state['player_connections']  # Don't save websocket SIDs

        # Convert UUIDs and datetimes to strings for JSON compatibility
        serializable_state = {}
        for key, value in state.items():
            if isinstance(value, uuid.UUID):
                serializable_state[key] = str(value)
            elif isinstance(value, datetime):
                serializable_state[key] = value.isoformat()
            elif isinstance(value, list) and value and isinstance(value[0], uuid.UUID):
                serializable_state[key] = [str(item) for item in value]
            elif isinstance(value, dict):
                # Handle dicts with UUID keys or values
                new_dict = {}
                for k, v in value.items():
                    new_k = str(k) if isinstance(k, uuid.UUID) else k
                    new_v = str(v) if isinstance(v, uuid.UUID) else v
                    new_dict[new_k] = new_v
                serializable_state[key] = new_dict
            else:
                serializable_state[key] = value
        return serializable_state

    @classmethod
    def deserialize_state(cls, state_data: Dict[str, Any]) -> 'GameSession':
        """Deserializes state data from DB into a GameSession object."""
        # Manually create instance without calling __init__ directly with all args
        # This allows restoring complex state without re-running setup logic.
        instance = cls.__new__(cls)

        # Convert relevant fields back from string/primitive types
        for key, value in state_data.items():
            # Convert UUIDs back
            if key in ['game_id', 'president_id', 'chancellor_candidate_id', 'chancellor_id'] and value:
                setattr(instance, key, uuid.UUID(value))
            elif key in ['initial_player_ids', 'players', 'executed_players'] and isinstance(value, list):
                setattr(instance, key, [uuid.UUID(item) for item in value])
            # Convert role dict keys back
            elif key == 'roles' and isinstance(value, dict):
                instance.roles = {uuid.UUID(k): v for k, v in value.items()}
            # Convert votes dict keys back
            elif key == 'votes' and isinstance(value, dict):
                instance.votes = {uuid.UUID(k): v for k, v in value.items()}
             # Convert last_government values back
            elif key == 'last_government' and isinstance(value, dict):
                instance.last_government = {
                    k: uuid.UUID(v) if v else None for k, v in value.items()
                    }
            # Convert datetimes back
            elif key in ['created_at', 'updated_at'] and isinstance(value, str):
                setattr(instance, key, datetime.fromisoformat(value))
            # Convert GameMode back from string
            elif key == 'mode' and isinstance(value, str):
                setattr(instance, key, GameMode(value))
             # Handle Enacted Policies Dict (keys are strings)
            elif key == 'enacted_policies' and isinstance(value, dict):
                instance.enacted_policies = value  # Assume keys are correct policy names
            # Default assignment for other types
            else:
                setattr(instance, key, value)

        # Initialize non-persistent fields
        instance.player_connections = {}

        print(f"GameSession {instance.game_id} deserialized.")
        return instance

    # --- Core Game Setup Methods ---
    def assign_roles(self):
        """Assigns roles to players based on player count and game mode."""
        if not self.players:
            raise RuntimeError("Cannot assign roles without players.")
        player_count = len(self.players)
        roles_to_assign: List[str] = []

        if self.mode == GameMode.NORMAL:
            # Formula for role distribution in NORMAL mode:
            # - Always 1 Hitler
            # - Fascists: (player_count - 1) // 2 - 1 (minimum 1)
            # - Liberals: player_count - fascists - 1
            fascist_count = max(1, (player_count - 1) // 2 - 1)
            liberal_count = player_count - fascist_count - 1
            
            roles_to_assign = ["Liberal"] * liberal_count + ["Fascist"] * fascist_count + ["Hitler"]
        elif self.mode == GameMode.XL:
            fascists_count = max(1, ((player_count-3) // 3)
                                 ) if player_count >= 5 else 0
            communists_count = max(
                 1, (player_count // 4)) if player_count >= 5 else 0
            capitalist_count = 1 if player_count > 10 else 0
            anarchist_count = 1 if player_count > 9 else 0
            monarchist_count = 1 if player_count > 12 else 0
            hitler_count = 1
            liberals_count = player_count - \
                (fascists_count + communists_count + capitalist_count +
                anarchist_count + monarchist_count + hitler_count)

            if liberals_count < 0:  # Sanity check
                raise ValueError(
                    f"Calculated negative liberals for {player_count} players in XL mode.")

            roles_to_assign.extend(["Liberal"] * liberals_count)
            roles_to_assign.extend(["Fascist"] * fascists_count)
            roles_to_assign.extend(["Communist"] * communists_count)
            roles_to_assign.extend(["Capitalist"] * capitalist_count)
            roles_to_assign.extend(["Anarchist"] * anarchist_count)
            roles_to_assign.extend(["Monarchist"] * monarchist_count)
            roles_to_assign.append("Hitler")

        else:
            raise ValueError(f"Unknown game mode: {self.mode}")

        if len(roles_to_assign) != player_count:
            raise RuntimeError(
                f"Mismatch between roles assigned ({len(roles_to_assign)}) and player count ({player_count}) for mode {self.mode}")

        random.shuffle(roles_to_assign)
        # Shuffle player order for assignment
        shuffled_players = list(self.players)
        random.shuffle(shuffled_players)

        self.roles = {player_id: role for player_id,
                      role in zip(shuffled_players, roles_to_assign)}
        print(f"Roles assigned for game {self.game_id}: {self.roles}")
        self._touch_updated_at()

    def initialize_deck(self):
        """Initializes and shuffles the policy deck based on game mode."""
        deck: List[str] = []
        if self.mode == GameMode.NORMAL:
            deck = ["Liberal"] * 6 + ["Fascist"] * 11
        elif self.mode == GameMode.XL:
            player_count = len(self.players)
            if player_count <= 9:
                deck = ['Communist']*8 + ['Liberal'] * 6 + ['Fascist'] * 9
            else:
                deck = ['Anti Fascist']*1 + ['Anti Communist']*1 + \
                    ['Communist']*7 + ['Liberal']*6 + \
                        ['Fascist']*9 + ['Anarchist']*2
        else:
            raise ValueError(
                f"Cannot initialize deck for unknown mode: {self.mode}")

        random.shuffle(deck)
        self.policies = deck
        self.discard_pile = []  # Ensure discard is empty
        print(
            f"Deck initialized for game {self.game_id} with {len(self.policies)} cards.")
        self._touch_updated_at()

    def _reshuffle_deck(self):
        """Shuffles the discard pile back into the draw pile."""
        if not self.discard_pile:
            raise RuntimeError("Cannot reshuffle deck: discard pile is empty.")
        print(
            f"Reshuffling discard pile ({len(self.discard_pile)} cards) into deck.")
        self.policies.extend(self.discard_pile)
        self.discard_pile = []
        random.shuffle(self.policies)
        self._touch_updated_at()

    def draw_policies(self, count: int) -> List[str]:
        """Draws a specified number of policies from the deck, reshuffling if necessary."""
        if len(self.policies) < count:
            print(
                f"Deck low ({len(self.policies)} cards), attempting reshuffle...")
            if len(self.policies) + len(self.discard_pile) < count:
                raise RuntimeError(
                    f"Cannot draw {count} policies: not enough cards remaining even after reshuffle.")
            self._reshuffle_deck()

        drawn = self.policies[:count]
        # Remove drawn policies from deck
        self.policies = self.policies[count:]
        print(
            f"Drew {count} policies: {drawn}. Deck remaining: {len(self.policies)}")
        self._touch_updated_at()
        return drawn

    # --- Placeholder for Next Steps ---
    def start_game_flow(self):
        """Initializes the game state after roles/deck are set."""
        if not self.roles or not self.policies:
            raise RuntimeError(
                "Cannot start game flow before assigning roles and initializing deck.")

        # Assign initial president (e.g., first player in the list)
        self.president_index = 0
        self.president_id = self.players[self.president_index]
        self.state = GamePhase.NOMINATION
        self._touch_updated_at()
        print(
            f"Game {self.game_id} starting. First president: {self.president_id}. State: {self.state}")
        # In a real scenario, this method would likely return data needed
        # for the WebSocket layer to emit the first 'election_started' event.
        return {
            "event": "election_started",
            "data": {
                "president_id": str(self.president_id),
                "eligible_chancellors": self.get_eligible_chancellor_candidates()
            }
        }

    def get_eligible_chancellor_candidates(self) -> List[str]:
        """Determines which players are eligible to be nominated as Chancellor."""
        if self.president_id is None:
            return []

        player_count = len(self.players)
        last_pres = self.last_government.get("president")
        last_chanc = self.last_government.get("chancellor")

        ineligible = {self.president_id}  # President cannot be Chancellor
        # Add last elected government members based on player count rule
        if player_count > 5:  # For >5 players, last Pres/Chanc are ineligible
            if last_pres:
                ineligible.add(last_pres)
            if last_chanc:
                ineligible.add(last_chanc)
        else:  # For 5 players, only last Chanc is ineligible
            if last_chanc:
                ineligible.add(last_chanc)

        # Filter out executed players
        ineligible.update(self.executed_players)

        eligible_ids = [
            str(p_id) for p_id in self.players if p_id not in ineligible
        ]
        return eligible_ids

    # Add more methods here later for:
    # - nominate_chancellor
    # - record_vote
    # - evaluate_votes
    # - president_discard_policy
    # - chancellor_enact_policy
    # - apply_executive_action
    # - check_win_conditions
    # - advance_to_next_president
    # - handle_chaos
