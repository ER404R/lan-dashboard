"""Tests for the dark/light mode theme toggle feature."""
import pytest

from tests.conftest import create_user, extract_csrf

TOGGLE_URL = "/theme/toggle"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client, db, username="themeuser", password="themepass1!"):
    """Create a user, log in, and return the client ready for authenticated calls."""
    create_user(db, username=username, password=password)
    resp = client.get("/login")
    csrf = extract_csrf(resp.text)
    client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": csrf},
        follow_redirects=False,
    )
    return client


def _get_csrf(client):
    """Fetch a valid CSRF token by visiting the home page (requires login)."""
    resp = client.get("/")
    return extract_csrf(resp.text)


# ---------------------------------------------------------------------------
# Theme toggle behaviour
# ---------------------------------------------------------------------------

class TestThemeToggle:
    def test_toggle_dark_to_light(self, client, db):
        """Starting in dark mode, toggling once sets theme to light."""
        _login(client, db)
        csrf = _get_csrf(client)

        # Default theme is dark — one POST should flip to light
        r = client.post(
            TOGGLE_URL,
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303

        # Subsequent page render must carry data-theme="light"
        home = client.get("/")
        assert 'data-theme="light"' in home.text

    def test_toggle_light_to_dark(self, client, db):
        """From light mode, toggling once sets theme back to dark."""
        _login(client, db)

        # First toggle: dark → light
        csrf = _get_csrf(client)
        client.post(TOGGLE_URL, data={"csrf_token": csrf}, follow_redirects=False)

        # Second toggle: light → dark
        csrf2 = _get_csrf(client)
        r = client.post(
            TOGGLE_URL,
            data={"csrf_token": csrf2},
            follow_redirects=False,
        )
        assert r.status_code == 303

        home = client.get("/")
        assert 'data-theme="dark"' in home.text

    def test_csrf_missing_token_rejected(self, client, db):
        """POST to /theme/toggle without a CSRF token must return 403."""
        _login(client, db)
        # Establish session without sending a csrf_token
        r = client.post(TOGGLE_URL, data={}, follow_redirects=False)
        assert r.status_code == 403

    def test_csrf_invalid_token_rejected(self, client, db):
        """POST to /theme/toggle with a tampered CSRF token must return 403."""
        _login(client, db)
        # Establish session by visiting a page first
        client.get("/")
        r = client.post(
            TOGGLE_URL,
            data={"csrf_token": "not-a-valid-signed-token"},
            follow_redirects=False,
        )
        assert r.status_code == 403

    def test_get_method_not_allowed(self, client, db):
        """GET /theme/toggle must return 405 Method Not Allowed."""
        _login(client, db)
        r = client.get(TOGGLE_URL, follow_redirects=False)
        assert r.status_code == 405

    def test_redirect_fallback_when_no_referer(self, client, db):
        """Without a Referer header the response must redirect to /."""
        _login(client, db)
        csrf = _get_csrf(client)

        # TestClient does not set Referer automatically
        r = client.post(
            TOGGLE_URL,
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/"

    def test_redirect_uses_referer_when_same_origin(self, client, db):
        """A same-origin Referer is honoured and the path is used for the redirect."""
        _login(client, db)
        csrf = _get_csrf(client)

        r = client.post(
            TOGGLE_URL,
            data={"csrf_token": csrf},
            headers={"referer": "http://testserver/features"},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/features"


# ---------------------------------------------------------------------------
# Default theme
# ---------------------------------------------------------------------------

class TestDefaultTheme:
    def test_default_theme_is_dark(self, client, db):
        """A freshly-logged-in user with no explicit theme preference sees dark mode."""
        _login(client, db)
        home = client.get("/")
        assert 'data-theme="dark"' in home.text


# ---------------------------------------------------------------------------
# Toggle button presence
# ---------------------------------------------------------------------------

class TestToggleButtonPresence:
    def test_toggle_button_visible_when_logged_in(self, client, db):
        """The theme-toggle form must appear in the nav for authenticated users."""
        _login(client, db)
        home = client.get("/")
        assert f'action="{TOGGLE_URL}"' in home.text

    def test_toggle_button_absent_when_logged_out(self, client):
        """Unauthenticated users must not see the theme-toggle button."""
        login_page = client.get("/login")
        assert f'action="{TOGGLE_URL}"' not in login_page.text
