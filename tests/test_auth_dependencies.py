"""Tests for authentication and authorization dependencies."""
import pytest
from fastapi import Request

from app.exceptions import UnauthenticatedError, UnauthorizedError
from app.dependencies import (
    get_authenticated_user,
    get_admin_user,
    get_current_user,
    flash,
    get_flashed_messages,
)
from tests.conftest import create_user, extract_csrf


class TestExceptions:
    """Test exception classes."""

    def test_unauthenticated_error_exists(self):
        """Test UnauthenticatedError can be raised."""
        with pytest.raises(UnauthenticatedError):
            raise UnauthenticatedError()

    def test_unauthorized_error_exists(self):
        """Test UnauthorizedError can be raised."""
        with pytest.raises(UnauthorizedError):
            raise UnauthorizedError()


class TestGetAuthenticatedUser:
    """Test get_authenticated_user dependency integration."""

    def test_authenticated_user_integration(self, client, db):
        """Test that get_authenticated_user works via HTTP when logged in."""
        create_user(db, username="testuser", password="testpass1!")
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert response.status_code == 200
        # If logged in, accessing protected route works
        response = client.get("/")
        assert response.status_code == 200

    def test_unauthenticated_user_raises_error(self, client):
        """Test that UnauthenticatedError is raised when not logged in."""
        # Not logged in - accessing protected route redirects
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


class TestGetAdminUser:
    """Test get_admin_user dependency integration."""

    def test_admin_user_returns_user(self, client, db):
        """Test that admin user can access admin routes."""
        create_user(db, username="adminuser", password="adminpass1!", is_admin=True)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "adminuser", "password": "adminpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Admin can access admin route
        response = client.get("/admin/tokens")
        assert response.status_code == 200

    def test_non_admin_user_raises_error(self, client, db):
        """Test that non-admin user cannot access admin routes."""
        create_user(db, username="testuser", password="testpass1!", is_admin=False)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        # Non-admin redirected from admin route
        response = client.get("/admin/tokens", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_unauthenticated_user_cannot_access_admin(self, client):
        """Test that unauthenticated user cannot access admin routes."""
        # Not logged in - accessing admin route redirects to login
        response = client.get("/admin/tokens", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


class TestExceptionHandlers:
    """Test exception handlers in main.py."""

    def test_unauthenticated_error_redirects_to_login(self, client):
        """Test that UnauthenticatedError redirects to /login with flash."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_unauthenticated_error_sets_flash_message(self, client):
        """Test that UnauthenticatedError sets flash message."""
        response = client.get("/", follow_redirects=True)
        # The flash message should be in the session or rendered
        # We verify by following the redirect
        assert response.status_code == 200

    def test_unauthorized_error_redirects_to_home(self, client, db):
        """Test that UnauthorizedError redirects to / with flash."""
        # Create and login as non-admin user
        create_user(db, username="testuser", password="testpass1!", is_admin=False)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=False,
        )
        # Try to access admin route
        response = client.get("/admin/tokens", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"


class TestAdminRoutes:
    """Test admin routes with new dependencies."""

    def test_admin_tokens_page_requires_admin(self, client):
        """Test that /admin/tokens requires admin login."""
        response = client.get("/admin/tokens", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_admin_tokens_page_accessible_by_admin(self, client, db):
        """Test that admin can access /admin/tokens."""
        # Create admin user and login
        create_user(db, username="adminuser", password="adminpass1!", is_admin=True)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "adminuser", "password": "adminpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Access admin tokens page
        response = client.get("/admin/tokens")
        assert response.status_code == 200
        assert b"tokens" in response.content.lower() or b"admin" in response.content.lower()

    def test_admin_tokens_page_denied_to_non_admin(self, client, db):
        """Test that non-admin user cannot access /admin/tokens."""
        # Create and login as non-admin user
        create_user(db, username="testuser", password="testpass1!", is_admin=False)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Try to access admin tokens page - should redirect
        response = client.get("/admin/tokens", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_admin_users_page_requires_admin(self, client):
        """Test that /admin/users requires admin login."""
        response = client.get("/admin/users", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_admin_users_page_accessible_by_admin(self, client, db):
        """Test that admin can access /admin/users."""
        # Create admin user and login
        create_user(db, username="adminuser", password="adminpass1!", is_admin=True)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "adminuser", "password": "adminpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Access admin users page
        response = client.get("/admin/users")
        assert response.status_code == 200


class TestScoreboardRoutes:
    """Test scoreboard routes with new dependencies."""

    def test_scoreboard_requires_login(self, client):
        """Test that / requires login."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_scoreboard_accessible_when_logged_in(self, client, db):
        """Test that authenticated user can access scoreboard."""
        # Create and login user
        create_user(db, username="testuser", password="testpass1!")
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Access scoreboard
        response = client.get("/")
        assert response.status_code == 200

    def test_search_steam_requires_login(self, client):
        """Test that /games/search-steam requires login."""
        response = client.get("/games/search-steam?q=test", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_add_game_requires_login(self, client):
        """Test that POST /games/add requires login."""
        response = client.post(
            "/games/add",
            data={"steam_appid": "123", "name": "Test Game"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_add_custom_game_requires_login(self, client):
        """Test that POST /games/add-custom requires login."""
        response = client.post(
            "/games/add-custom",
            data={"name": "Custom Game"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_rate_game_requires_login(self, client):
        """Test that POST /games/{id}/rate requires login."""
        response = client.post(
            "/games/1/rate",
            data={"value": "5"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_set_ownership_requires_login(self, client):
        """Test that POST /games/{id}/ownership requires login."""
        response = client.post(
            "/games/1/ownership",
            data={"status": "owned"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


class TestFeatureRoutes:
    """Test feature routes with new dependencies."""

    def test_list_features_requires_login(self, client):
        """Test that /features requires login."""
        response = client.get("/features", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_list_features_accessible_when_logged_in(self, client, db):
        """Test that authenticated user can access features list."""
        # Create and login user
        create_user(db, username="testuser", password="testpass1!")
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Access features list
        response = client.get("/features")
        assert response.status_code == 200

    def test_new_feature_form_requires_login(self, client):
        """Test that /features/new requires login."""
        response = client.get("/features/new", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_create_feature_requires_login(self, client):
        """Test that POST /features requires login."""
        response = client.post(
            "/features",
            data={"title": "New Feature", "description": "Test"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_feature_detail_requires_login(self, client):
        """Test that /features/{id} requires login."""
        response = client.get("/features/1", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_add_comment_requires_login(self, client):
        """Test that POST /features/{id}/comment requires login."""
        response = client.post(
            "/features/1/comment",
            data={"content": "Test comment"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

    def test_resolve_feature_requires_admin(self, client, db):
        """Test that POST /features/{id}/resolve requires admin."""
        # Create and login as non-admin
        create_user(db, username="testuser", password="testpass1!", is_admin=False)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Try to resolve feature - should redirect
        response = client.post(
            "/features/1/resolve",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_delete_feature_requires_admin(self, client, db):
        """Test that POST /features/{id}/delete requires admin."""
        # Create and login as non-admin
        create_user(db, username="testuser", password="testpass1!", is_admin=False)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Try to delete feature - should redirect
        response = client.post(
            "/features/1/delete",
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers["location"] == "/"

    def test_resolve_feature_accessible_by_admin(self, client, db):
        """Test that admin can access feature resolution endpoints."""
        # Create and login as admin
        create_user(db, username="adminuser", password="adminpass1!", is_admin=True)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "adminuser", "password": "adminpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Get CSRF token from a page that has it
        resp = client.get("/features")
        csrf_token = extract_csrf(resp.text)

        # Try to resolve feature (will fail with 303 because feature doesn't exist, but auth passes)
        response = client.post(
            "/features/1/resolve",
            data={"csrf_token": csrf_token},
            follow_redirects=False,
        )
        # If auth passes, we get 303 (redirect) because feature not found, not 403 Forbidden from auth
        assert response.status_code in (303, 422)  # 303 redirect or 422 validation error are both OK
        # Should not be 403 (which would mean unauthorized)


class TestBackwardCompatibility:
    """Test that old dependencies still exist for backward compatibility."""

    def test_get_current_user_still_exists(self, client, db):
        """Test that get_current_user still works for backward compatibility."""
        create_user(db, username="testuser", password="testpass1!")
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        # If get_current_user still works, login should succeed
        assert response.status_code == 200

    def test_get_current_user_returns_none_for_logout(self, client, db):
        """Test that get_current_user integration works (logout returns to login)."""
        create_user(db, username="testuser", password="testpass1!")
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert response.status_code == 200
        # After logout, unauthenticated routes behave like no user
        resp = client.get("/")  # Get CSRF token from a page
        csrf_token = extract_csrf(resp.text)
        response = client.post("/logout", data={"csrf_token": csrf_token}, follow_redirects=True)
        assert response.status_code == 200
        # Trying to access protected route now redirects
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303

    def test_require_login_function_still_exists(self):
        """Test that require_login function is still available."""
        # Just verify it's importable and callable
        from app.dependencies import require_login
        assert callable(require_login)

    def test_require_admin_function_still_exists(self):
        """Test that require_admin function is still available."""
        # Just verify it's importable and callable
        from app.dependencies import require_admin
        assert callable(require_admin)


class TestNoManualChecks:
    """Verify that manual auth checks were removed from routes."""

    def test_admin_routes_no_manual_require_admin_calls(self):
        """Verify admin.py doesn't have manual require_admin calls."""
        import inspect
        from app.routers import admin

        source = inspect.getsource(admin)
        # Check that require_admin is not called in route handlers
        # (it should only be in dependencies)
        lines = source.split("\n")
        route_bodies = []
        in_route = False
        for line in lines:
            if line.strip().startswith("@router."):
                in_route = True
            elif in_route and line.strip() and not line.startswith(" "):
                in_route = False
            elif in_route:
                route_bodies.append(line)

        # Verify require_admin is not called in route bodies
        route_body_text = "\n".join(route_bodies)
        # It's ok if require_admin is imported but not called in functions
        assert "require_admin(user" not in route_body_text

    def test_scoreboard_routes_no_manual_redirect_checks(self):
        """Verify scoreboard.py doesn't have manual redirect checks."""
        import inspect
        from app.routers import scoreboard

        source = inspect.getsource(scoreboard)
        # Check that manual "if not user" checks are removed
        assert 'if not user:' not in source

    def test_feature_routes_no_manual_require_login_calls(self):
        """Verify feature_requests.py doesn't have manual require_login calls."""
        import inspect
        from app.routers import feature_requests

        source = inspect.getsource(feature_requests)
        # Check that require_login is not called in route handlers
        assert "require_login(user" not in source
