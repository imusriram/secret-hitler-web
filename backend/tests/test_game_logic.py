# backend/tests/test_game_logic.py
import pytest
import uuid
from datetime import datetime
from app.services.game_logic import GameSession, GameMode, GamePhase


@pytest.fixture
def player_ids_5():
    return [uuid.uuid4() for _ in range(5)]


@pytest.fixture
def player_ids_11():
    return [uuid.uuid4() for _ in range(11)]


def test_game_initialization(player_ids_5):
    game_id = uuid.uuid4()
    session = GameSession(
        game_id=game_id, player_ids=player_ids_5, mode=GameMode.NORMAL)
    assert session.game_id == game_id
    assert session.players == player_ids_5
    assert session.mode == GameMode.NORMAL
    assert session.status == GamePhase.STARTING
    assert not session.roles  # Roles not assigned yet
    assert not session.policies  # Deck not initialized yet


def test_assign_roles_normal_5_players(player_ids_5):
    session = GameSession(game_id=uuid.uuid4(),
                          player_ids=player_ids_5, mode=GameMode.NORMAL)
    session.assign_roles()
    assert len(session.roles) == 5
    roles_list = list(session.roles.values())
    assert roles_list.count("Liberal") == 3
    assert roles_list.count("Fascist") == 1
    assert roles_list.count("Hitler") == 1
    # Check all players got a role
    assert set(session.roles.keys()) == set(player_ids_5)


def test_assign_roles_xl_11_players(player_ids_11):
    session = GameSession(game_id=uuid.uuid4(),
                          player_ids=player_ids_11, mode=GameMode.XL)
    session.assign_roles()
    # Based on bot logic: 11 -> F=2, C=2, Cap=1, Ana=1, Mon=0, H=1 => L=4
    assert len(session.roles) == 11
    roles_list = list(session.roles.values())
    assert roles_list.count("Liberal") == 4
    assert roles_list.count("Fascist") == 2
    assert roles_list.count("Communist") == 2
    assert roles_list.count("Capitalist") == 1
    assert roles_list.count("Anarchist") == 1
    assert roles_list.count("Monarchist") == 0
    assert roles_list.count("Hitler") == 1
    assert set(session.roles.keys()) == set(player_ids_11)


def test_initialize_deck_normal(player_ids_5):
    session = GameSession(game_id=uuid.uuid4(),
                          player_ids=player_ids_5, mode=GameMode.NORMAL)
    session.initialize_deck()
    assert len(session.policies) == 17  # 6 L + 11 F
    assert session.policies.count("Liberal") == 6
    assert session.policies.count("Fascist") == 11
    assert not session.discard_pile


def test_initialize_deck_xl_11_players(player_ids_11):
    session = GameSession(game_id=uuid.uuid4(),
                          player_ids=player_ids_11, mode=GameMode.XL)
    session.initialize_deck()
    # 1 AF + 1 AC + 7 C + 6 L + 9 F + 2 A = 26 cards
    assert len(session.policies) == 26
    assert session.policies.count("Liberal") == 6
    assert session.policies.count("Fascist") == 9
    assert session.policies.count("Communist") == 7
    assert session.policies.count("Anarchist") == 2
    assert session.policies.count("Anti Fascist") == 1
    assert session.policies.count("Anti Communist") == 1
    assert not session.discard_pile


def test_serialization_deserialization(player_ids_5):
    game_id = uuid.uuid4()
    session = GameSession(
        game_id=game_id, player_ids=player_ids_5, mode=GameMode.NORMAL)
    session.assign_roles()
    session.initialize_deck()
    session.start_game_flow()  # Set president, state etc.
    session.election_tracker = 1  # Change some state

    # Simulate drawing policies
    drawn = session.draw_policies(3)
    session.policies_drawn_for_legislative = drawn
    session.state = GamePhase.LEGISLATIVE_PRESIDENT_DISCARD

    serialized_data = session.serialize_state()

    # Basic checks on serialized data
    assert serialized_data['game_id'] == str(game_id)
    assert serialized_data['mode'] == 'Normal'
    assert serialized_data['state'] == GamePhase.LEGISLATIVE_PRESIDENT_DISCARD
    assert serialized_data['election_tracker'] == 1
    assert isinstance(serialized_data['created_at'], str)
    assert isinstance(serialized_data['roles'], dict)
    assert isinstance(serialized_data['players'], list)
    assert isinstance(serialized_data['policies_drawn_for_legislative'], list)
    assert all(isinstance(p, str) for p in serialized_data['players'])
    # Ensure non-persistent field excluded
    assert 'player_connections' not in serialized_data

    # Deserialize
    restored_session = GameSession.deserialize_state(serialized_data)

    # Check restored fields (add more checks as needed)
    assert restored_session.game_id == game_id
    assert restored_session.players == player_ids_5
    assert restored_session.mode == GameMode.NORMAL
    assert restored_session.state == GamePhase.LEGISLATIVE_PRESIDENT_DISCARD
    assert restored_session.election_tracker == 1
    assert len(restored_session.policies) == 14  # 17 initial - 3 drawn
    assert restored_session.policies_drawn_for_legislative == drawn
    # Check roles dictionary restored correctly
    assert restored_session.roles == session.roles
    assert isinstance(restored_session.created_at, datetime)
    assert restored_session.player_connections == {}  # Should be empty


def test_draw_policies_reshuffle(player_ids_5):
    session = GameSession(game_id=uuid.uuid4(),
                          player_ids=player_ids_5, mode=GameMode.NORMAL)
    session.initialize_deck()
    initial_deck_size = len(session.policies)

    # Draw almost all policies
    for _ in range(initial_deck_size // 3):
        session.draw_policies(3)  # Simulate drawing 3
        session.discard_pile.extend(
            ["Fascist", "Fascist", "Liberal"])  # Simulate discard/enact

    # Make deck low
    session.policies = session.policies[-2:]  # Leave only 2 cards

    # Try drawing 3 - should trigger reshuffle
    drawn = session.draw_policies(3)
    assert len(drawn) == 3
    # New deck size should be original - 3 (just drawn)
    assert len(session.policies) == initial_deck_size - 3
    assert not session.discard_pile  # Discard should be empty after reshuffle
