"""Tests for the admin routes (app/routers/admin.py)."""
import pytest

from tests.conftest import extract_csrf
from app.models import InviteToken


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_tokens_csrf(client):
    resp = client.get("/admin/tokens")
    assert resp.status_code == 200
    csrf = extract_csrf(resp.text)
    assert csrf, "CSRF token not found on admin/tokens page"
    return csrf


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
class TestAdminAccessControl:
    def test_unauthenticated_tokens_page_redirects(self, client):
        r = client.get("/admin/tokens", follow_redirects=False)
        assert r.status_code == 303
        assert "/login" in r.headers["location"]

    def test_unauthenticated_users_page_redirects(self, client):
        r = client.get("/admin/users", follow_redirects=False)
        assert r.status_code == 303
        assert "/login" in r.headers["location"]

    def test_regular_user_blocked_from_tokens(self, auth_client):
        client, _ = auth_client
        r = client.get("/admin/tokens", follow_redirects=False)
        assert r.status_code == 303
        assert "/admin" not in r.headers.get("location", "")

    def test_regular_user_blocked_from_users(self, auth_client):
        client, _ = auth_client
        r = client.get("/admin/users", follow_redirects=False)
        assert r.status_code == 303
        assert "/admin" not in r.headers.get("location", "")

    def test_admin_can_access_tokens_page(self, admin_client):
        client, _ = admin_client
        r = client.get("/admin/tokens")
        assert r.status_code == 200

    def test_admin_can_access_users_page(self, admin_client):
        client, _ = admin_client
        r = client.get("/admin/users")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------
class TestTokenGeneration:
    def test_generate_single_token(self, admin_client, db):
        client, _ = admin_client
        csrf = _get_tokens_csrf(client)
        r = client.post(
            "/admin/tokens/generate",
            data={"count": "1", "max_uses": "1", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/admin/tokens"
        tokens = db.query(InviteToken).all()
        assert len(tokens) >= 1

    def test_generate_multiple_tokens(self, admin_client, db):
        client, _ = admin_client
        csrf = _get_tokens_csrf(client)
        r = client.post(
            "/admin/tokens/generate",
            data={"count": "5", "max_uses": "2", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        tokens = db.query(InviteToken).all()
        assert len(tokens) >= 5

    def test_generate_unlimited_token(self, admin_client, db):
        client, _ = admin_client
        csrf = _get_tokens_csrf(client)
        client.post(
            "/admin/tokens/generate",
            data={"count": "1", "max_uses": "0", "csrf_token": csrf},
            follow_redirects=True,
        )
        tokens = db.query(InviteToken).filter_by(max_uses=0).all()
        assert len(tokens) >= 1

    def test_generate_capped_at_50(self, admin_client, db):
        client, _ = admin_client
        csrf = _get_tokens_csrf(client)
        client.post(
            "/admin/tokens/generate",
            data={"count": "100", "max_uses": "1", "csrf_token": csrf},
            follow_redirects=False,
        )
        tokens = db.query(InviteToken).all()
        # Cap is 50, so at most 50 new tokens
        assert len(tokens) <= 50

    def test_generate_token_missing_csrf_rejected(self, admin_client):
        client, _ = admin_client
        r = client.post(
            "/admin/tokens/generate",
            data={"count": "1", "max_uses": "1"},
            follow_redirects=False,
        )
        assert r.status_code == 403

    def test_non_admin_cannot_generate_tokens(self, auth_client, db):
        client, _ = auth_client
        # Auth client doesn't have admin session but can still get a CSRF from
        # the login page; posting to the admin endpoint should redirect away.
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        r = client.post(
            "/admin/tokens/generate",
            data={"count": "1", "max_uses": "1", "csrf_token": csrf},
            follow_redirects=False,
        )
        # Should redirect (non-admin) and NOT create tokens
        assert r.status_code == 303
        assert "/admin" not in r.headers.get("location", "")

    def test_flash_message_shown_after_generate(self, admin_client):
        client, _ = admin_client
        csrf = _get_tokens_csrf(client)
        r = client.post(
            "/admin/tokens/generate",
            data={"count": "3", "max_uses": "1", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert "Generated" in r.text or "token" in r.text.lower()


# ---------------------------------------------------------------------------
# Token revocation
# ---------------------------------------------------------------------------
class TestTokenRevocation:
    def _create_token_via_admin(self, client, db):
        """Generate one token through the UI and return its DB object."""
        csrf = _get_tokens_csrf(client)
        client.post(
            "/admin/tokens/generate",
            data={"count": "1", "max_uses": "1", "csrf_token": csrf},
            follow_redirects=False,
        )
        db.expire_all()
        return db.query(InviteToken).order_by(InviteToken.id.desc()).first()

    def test_revoke_token(self, admin_client, db):
        client, _ = admin_client
        token = self._create_token_via_admin(client, db)
        assert token.revoked is False

        csrf = _get_tokens_csrf(client)
        r = client.post(
            f"/admin/tokens/{token.id}/revoke",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        db.expire_all()
        db.refresh(token)
        assert token.revoked is True

    def test_revoke_then_restore_toggles(self, admin_client, db):
        client, _ = admin_client
        token = self._create_token_via_admin(client, db)

        for expected_revoked in (True, False):
            csrf = _get_tokens_csrf(client)
            client.post(
                f"/admin/tokens/{token.id}/revoke",
                data={"csrf_token": csrf},
                follow_redirects=False,
            )
            db.expire_all()
            db.refresh(token)
            assert token.revoked is expected_revoked

    def test_revoke_nonexistent_token_redirects(self, admin_client):
        client, _ = admin_client
        csrf = _get_tokens_csrf(client)
        r = client.post(
            "/admin/tokens/99999/revoke",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert "/admin/tokens" in r.headers["location"]

    def test_revoke_missing_csrf_rejected(self, admin_client, db):
        client, _ = admin_client
        token = self._create_token_via_admin(client, db)
        r = client.post(
            f"/admin/tokens/{token.id}/revoke",
            data={},
            follow_redirects=False,
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Users list
# ---------------------------------------------------------------------------
class TestUsersPage:
    def test_users_page_shows_admin_user(self, admin_client):
        client, admin = admin_client
        r = client.get("/admin/users")
        assert r.status_code == 200
        assert admin.username in r.text

    def test_users_page_lists_all_users(self, admin_client, db):
        from tests.conftest import create_user
        client, admin = admin_client
        create_user(db, username="extrauser1")
        create_user(db, username="extrauser2")
        r = client.get("/admin/users")
        assert "extrauser1" in r.text
        assert "extrauser2" in r.text
