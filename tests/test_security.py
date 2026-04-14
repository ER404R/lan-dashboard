"""Tests for security headers, CSRF protection, auth guards, and startup validation."""
import pytest

from tests.conftest import create_user, extract_csrf


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
class TestSecurityHeaders:
    def test_required_headers_present(self, client, db):
        """All mandatory security headers must be present on every response."""
        create_user(db)
        resp = client.get("/login")
        headers = resp.headers

        assert "X-Content-Type-Options" in headers
        assert headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in headers
        assert headers["X-Frame-Options"] == "DENY"

        assert "Referrer-Policy" in headers

        assert "Content-Security-Policy" in headers
        csp = headers["Content-Security-Policy"]
        assert "default-src" in csp
        assert "frame-ancestors" in csp

        assert "Strict-Transport-Security" in headers
        hsts = headers["Strict-Transport-Security"]
        assert "max-age" in hsts
        assert "includeSubDomains" in hsts

        assert "X-XSS-Protection" in headers
        assert "Permissions-Policy" in headers

    def test_csp_allows_known_cdns(self, client, db):
        resp = client.get("/login")
        csp = resp.headers["Content-Security-Policy"]
        # pico.css CDN
        assert "cdn.jsdelivr.net" in csp
        # htmx CDN
        assert "unpkg.com" in csp


# ---------------------------------------------------------------------------
# Session cookie flags
# ---------------------------------------------------------------------------
class TestSessionCookie:
    def test_session_cookie_has_secure_flag(self, client, db):
        """The session cookie must carry the Secure flag so it is never sent over HTTP."""
        create_user(db)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        # POST login to trigger session cookie issuance
        r = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303  # confirm login succeeded

        # Inspect the Set-Cookie header for the session cookie
        set_cookie = r.headers.get("set-cookie", "")
        assert "session" in set_cookie, "Expected session cookie to be set after login"
        assert "secure" in set_cookie.lower(), (
            "Session cookie is missing the Secure flag — "
            "it could be transmitted over plain HTTP"
        )

    def test_session_cookie_has_httponly_flag(self, client, db):
        """The session cookie must carry HttpOnly to block JS access."""
        create_user(db)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        r = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        set_cookie = r.headers.get("set-cookie", "")
        assert "httponly" in set_cookie.lower(), (
            "Session cookie is missing the HttpOnly flag"
        )


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------
class TestCSRF:
    def test_csrf_missing_token_rejected(self, client, db):
        """POST without any csrf_token must return 403."""
        create_user(db)
        r = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!"},
            follow_redirects=False,
        )
        assert r.status_code == 403

    def test_csrf_invalid_token_rejected(self, client, db):
        """POST with a tampered/wrong csrf_token must return 403."""
        create_user(db)
        # Establish session first
        client.get("/login")
        r = client.post(
            "/login",
            data={
                "username": "testuser",
                "password": "testpass1!",
                "csrf_token": "totally-invalid-token",
            },
            follow_redirects=False,
        )
        assert r.status_code == 403

    def test_csrf_valid_token_accepted(self, client, db):
        """POST with a valid csrf_token must succeed (not 403)."""
        create_user(db)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        assert csrf, "CSRF token not found in login page HTML"

        r = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=False,
        )
        # Should redirect (303) rather than 403
        assert r.status_code == 303


# ---------------------------------------------------------------------------
# Startup validation
# ---------------------------------------------------------------------------
class TestStartupValidation:
    def test_weak_secret_key_raises_runtime_error(self):
        """Settings constructed with the default SECRET_KEY must raise RuntimeError."""
        from app.config import Settings

        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            Settings(SECRET_KEY="change-me-in-production")

    def test_strong_secret_key_accepted(self):
        """Settings with a proper key must not raise."""
        from app.config import Settings

        s = Settings(SECRET_KEY="a-proper-random-secret-key-12345!")
        assert s.SECRET_KEY == "a-proper-random-secret-key-12345!"


# ---------------------------------------------------------------------------
# Authentication guards
# ---------------------------------------------------------------------------
class TestAuthGuards:
    def test_unauthenticated_scoreboard_redirects(self, client):
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 303
        assert "/login" in r.headers["location"]

    def test_unauthenticated_features_redirects(self, client):
        r = client.get("/features", follow_redirects=False)
        assert r.status_code == 303
        assert "/login" in r.headers["location"]

    def test_unauthenticated_admin_redirects(self, client):
        r = client.get("/admin/tokens", follow_redirects=False)
        assert r.status_code == 303
        assert "/login" in r.headers["location"]

    def test_non_admin_blocked_from_admin(self, auth_client):
        client, _ = auth_client
        r = client.get("/admin/tokens", follow_redirects=False)
        # Regular users get redirected away from admin
        assert r.status_code == 303
        assert "/admin" not in r.headers.get("location", "/admin")
