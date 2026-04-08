"""Tests for the scoreboard routes (game listing, adding, rating, ownership)."""
import pytest

from tests.conftest import (
    create_game,
    create_user,
    extract_csrf,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_scoreboard_csrf(client):
    """Visit the scoreboard and return the embedded CSRF token."""
    resp = client.get("/")
    assert resp.status_code == 200, f"scoreboard GET failed: {resp.status_code}"
    csrf = extract_csrf(resp.text)
    assert csrf, "CSRF token not found on scoreboard page"
    return csrf


# ---------------------------------------------------------------------------
# Adding steam games
# ---------------------------------------------------------------------------
class TestAddGame:
    def test_add_game_success(self, auth_client, db):
        client, user = auth_client
        csrf = _get_scoreboard_csrf(client)
        r = client.post(
            "/games/add",
            data={
                "steam_appid": "123456",
                "name": "Half-Life 3",
                "thumbnail_url": "https://example.com/img.jpg",
                "steam_url": "https://store.steampowered.com/app/123456",
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/"
        from app.models import Game
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            game = s.query(Game).filter_by(steam_appid=123456).first()
            assert game is not None
            assert game.name == "Half-Life 3"

    def test_add_duplicate_game_blocked(self, auth_client, db):
        client, user = auth_client
        create_game(db, name="Existing Game", added_by_id=user.id, steam_appid=999)
        csrf = _get_scoreboard_csrf(client)
        r = client.post(
            "/games/add",
            data={
                "steam_appid": "999",
                "name": "Existing Game",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert "already on the scoreboard" in r.text

    def test_unauthenticated_add_game_blocked(self, client):
        # No session => CSRF check fires (no session token), returns 403
        r = client.post(
            "/games/add",
            data={"steam_appid": "1", "name": "X", "csrf_token": "fake"},
            follow_redirects=False,
        )
        assert r.status_code in (303, 403)


# ---------------------------------------------------------------------------
# URL validation for steam games
# ---------------------------------------------------------------------------
class TestAddGameUrlValidation:
    """steam_url and thumbnail_url must be validated in /games/add."""

    def test_javascript_steam_url_rejected(self, auth_client, db):
        client, user = auth_client
        csrf = _get_scoreboard_csrf(client)
        r = client.post(
            "/games/add",
            data={
                "steam_appid": "111111",
                "name": "Evil Game",
                "steam_url": "javascript:evil()",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "http" in r.text or "URL" in r.text
        from app.models import Game
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            assert s.query(Game).filter_by(steam_appid=111111).first() is None

    def test_javascript_thumbnail_url_rejected(self, auth_client, db):
        client, user = auth_client
        csrf = _get_scoreboard_csrf(client)
        r = client.post(
            "/games/add",
            data={
                "steam_appid": "222222",
                "name": "Evil Thumb",
                "steam_url": "https://store.steampowered.com/app/222222",
                "thumbnail_url": "javascript:evil()",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "http" in r.text or "URL" in r.text
        from app.models import Game
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            assert s.query(Game).filter_by(steam_appid=222222).first() is None

    def test_data_uri_steam_url_rejected(self, auth_client, db):
        client, user = auth_client
        csrf = _get_scoreboard_csrf(client)
        r = client.post(
            "/games/add",
            data={
                "steam_appid": "333333",
                "name": "Data Game",
                "steam_url": "data:text/html,<script>alert(1)</script>",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        from app.models import Game
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            assert s.query(Game).filter_by(steam_appid=333333).first() is None

    def test_valid_https_urls_accepted(self, auth_client, db):
        """Legitimate Steam URLs must still be accepted."""
        client, user = auth_client
        csrf = _get_scoreboard_csrf(client)
        r = client.post(
            "/games/add",
            data={
                "steam_appid": "444444",
                "name": "Valid Game",
                "steam_url": "https://store.steampowered.com/app/444444",
                "thumbnail_url": "https://cdn.akamai.steamstatic.com/img.jpg",
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        from app.models import Game
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            game = s.query(Game).filter_by(steam_appid=444444).first()
            assert game is not None
            assert game.steam_url == "https://store.steampowered.com/app/444444"


# ---------------------------------------------------------------------------
# Adding custom (non-Steam) games
# ---------------------------------------------------------------------------
class TestAddCustomGame:
    def test_add_custom_game_success(self, auth_client, db):
        client, user = auth_client
        csrf = _get_scoreboard_csrf(client)
        r = client.post(
            "/games/add-custom",
            data={"name": "Catan", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        from app.models import Game
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            game = s.query(Game).filter_by(name="Catan").first()
            assert game is not None
            assert game.steam_appid is None

    def test_add_custom_game_name_too_long(self, auth_client, db):
        client, user = auth_client
        csrf = _get_scoreboard_csrf(client)
        long_name = "A" * 256
        r = client.post(
            "/games/add-custom",
            data={"name": long_name, "csrf_token": csrf},
            follow_redirects=True,
        )
        assert "255" in r.text or "at most" in r.text

    def test_add_custom_game_invalid_url(self, auth_client, db):
        client, user = auth_client
        csrf = _get_scoreboard_csrf(client)
        r = client.post(
            "/games/add-custom",
            data={
                "name": "Catan",
                "thumbnail_url": "javascript:evil()",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert "http" in r.text or "URL" in r.text

    def test_add_custom_game_duplicate_blocked(self, auth_client, db):
        client, user = auth_client
        csrf = _get_scoreboard_csrf(client)
        client.post(
            "/games/add-custom",
            data={"name": "Monopoly", "csrf_token": csrf},
            follow_redirects=False,
        )
        csrf2 = _get_scoreboard_csrf(client)
        r = client.post(
            "/games/add-custom",
            data={"name": "Monopoly", "csrf_token": csrf2},
            follow_redirects=True,
        )
        assert "already on the scoreboard" in r.text

    def test_add_custom_game_missing_csrf(self, auth_client, db):
        client, _ = auth_client
        r = client.post(
            "/games/add-custom",
            data={"name": "Catan"},
            follow_redirects=False,
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Rating games
# ---------------------------------------------------------------------------
class TestRateGame:
    def test_rate_game_success(self, auth_client, db):
        client, user = auth_client
        game = create_game(db, name="Portal", added_by_id=user.id)
        csrf = _get_scoreboard_csrf(client)
        r = client.post(
            f"/games/{game.id}/rate",
            data={"value": "8", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        from app.models import Score
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            score = s.query(Score).filter_by(user_id=user.id, game_id=game.id).first()
            assert score is not None
            assert score.value == 8

    def test_rate_game_upsert(self, auth_client, db):
        """Rating the same game twice should update the existing score."""
        client, user = auth_client
        game = create_game(db, name="Portal", added_by_id=user.id)
        for value in (7, 9):
            csrf = _get_scoreboard_csrf(client)
            client.post(
                f"/games/{game.id}/rate",
                data={"value": str(value), "csrf_token": csrf},
                follow_redirects=False,
            )
        from app.models import Score
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            scores = s.query(Score).filter_by(user_id=user.id, game_id=game.id).all()
            assert len(scores) == 1
            assert scores[0].value == 9

    def test_rate_out_of_range(self, auth_client, db):
        client, user = auth_client
        game = create_game(db, name="Portal", added_by_id=user.id)
        csrf = _get_scoreboard_csrf(client)
        r = client.post(
            f"/games/{game.id}/rate",
            data={"value": "11", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert "between 0 and 10" in r.text or "Rating" in r.text

    def test_rate_missing_csrf(self, auth_client, db):
        client, user = auth_client
        game = create_game(db, name="Portal", added_by_id=user.id)
        r = client.post(
            f"/games/{game.id}/rate",
            data={"value": "5"},
            follow_redirects=False,
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Game ownership
# ---------------------------------------------------------------------------
class TestOwnership:
    def test_ownership_set_owned(self, auth_client, db):
        client, user = auth_client
        game = create_game(db, name="Terraria", added_by_id=user.id)
        csrf = _get_scoreboard_csrf(client)
        r = client.post(
            f"/games/{game.id}/ownership",
            data={"status": "owned", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        from app.models import GameOwnership
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            ow = s.query(GameOwnership).filter_by(user_id=user.id, game_id=game.id).first()
            assert ow is not None
            assert ow.status == "owned"

    def test_ownership_set_want(self, auth_client, db):
        client, user = auth_client
        game = create_game(db, name="Terraria", added_by_id=user.id)
        csrf = _get_scoreboard_csrf(client)
        r = client.post(
            f"/games/{game.id}/ownership",
            data={"status": "want", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        from app.models import GameOwnership
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            ow = s.query(GameOwnership).filter_by(user_id=user.id, game_id=game.id).first()
            assert ow is not None
            assert ow.status == "want"

    def test_ownership_set_none_removes_record(self, auth_client, db):
        client, user = auth_client
        game = create_game(db, name="Terraria", added_by_id=user.id)
        csrf = _get_scoreboard_csrf(client)
        client.post(
            f"/games/{game.id}/ownership",
            data={"status": "owned", "csrf_token": csrf},
            follow_redirects=False,
        )
        csrf2 = _get_scoreboard_csrf(client)
        client.post(
            f"/games/{game.id}/ownership",
            data={"status": "none", "csrf_token": csrf2},
            follow_redirects=False,
        )
        from app.models import GameOwnership
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            ow = s.query(GameOwnership).filter_by(user_id=user.id, game_id=game.id).first()
            assert ow is None

    def test_ownership_missing_csrf(self, auth_client, db):
        client, user = auth_client
        game = create_game(db, name="Terraria", added_by_id=user.id)
        r = client.post(
            f"/games/{game.id}/ownership",
            data={"status": "owned"},
            follow_redirects=False,
        )
        assert r.status_code == 403
