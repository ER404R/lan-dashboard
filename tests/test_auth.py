"""Tests for authentication routes (login, register, logout)."""
from tests.conftest import (
    create_invite_token,
    create_user,
    extract_csrf,
)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
class TestLogin:
    def test_login_success(self, client, db):
        create_user(db)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        r = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/"

    def test_login_wrong_password(self, client, db):
        create_user(db)
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        r = client.post(
            "/login",
            data={"username": "testuser", "password": "wrongpass", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert "Invalid username or password" in r.text

    def test_login_unknown_user(self, client, db):
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        r = client.post(
            "/login",
            data={"username": "nobody", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=True,
        )
        # Same error message — no username enumeration
        assert "Invalid username or password" in r.text

    def test_login_missing_csrf_rejected(self, client, db):
        create_user(db)
        # Ensure session has no _csrf_token first; POST without token
        r = client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!"},
            follow_redirects=False,
        )
        assert r.status_code == 403

    def test_login_redirect_if_already_logged_in(self, auth_client):
        client, _ = auth_client
        r = client.get("/login", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
class TestRegister:
    def test_register_success(self, client, db):
        create_invite_token(db, token="good-token")
        resp = client.get("/register")
        csrf = extract_csrf(resp.text)
        r = client.post(
            "/register",
            data={
                "username": "newuser",
                "password": "newpass1!",
                "invite_token": "good-token",
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/login"

    def test_register_invalid_token(self, client, db):
        resp = client.get("/register")
        csrf = extract_csrf(resp.text)
        r = client.post(
            "/register",
            data={
                "username": "newuser",
                "password": "newpass1!",
                "invite_token": "bad-token",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert "Invalid" in r.text or "revoked" in r.text or "exhausted" in r.text

    def test_register_exhausted_token(self, client, db):
        it = create_invite_token(db, token="used-token", max_uses=1)
        it.use_count = 1
        db.commit()
        resp = client.get("/register")
        csrf = extract_csrf(resp.text)
        r = client.post(
            "/register",
            data={
                "username": "newuser",
                "password": "newpass1!",
                "invite_token": "used-token",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert "Invalid" in r.text or "exhausted" in r.text

    def test_register_revoked_token(self, client, db):
        create_invite_token(db, token="revoked-token", revoked=True)
        resp = client.get("/register")
        csrf = extract_csrf(resp.text)
        r = client.post(
            "/register",
            data={
                "username": "newuser",
                "password": "newpass1!",
                "invite_token": "revoked-token",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert "Invalid" in r.text or "revoked" in r.text

    def test_register_duplicate_username(self, client, db):
        create_user(db, username="existing")
        create_invite_token(db, token="dup-token")
        resp = client.get("/register")
        csrf = extract_csrf(resp.text)
        r = client.post(
            "/register",
            data={
                "username": "existing",
                "password": "newpass1!",
                "invite_token": "dup-token",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert "taken" in r.text or "already" in r.text

    def test_register_password_too_short(self, client, db):
        create_invite_token(db, token="short-pw-token")
        resp = client.get("/register")
        csrf = extract_csrf(resp.text)
        r = client.post(
            "/register",
            data={
                "username": "newuser",
                "password": "short",  # 5 chars — below the 8-char minimum
                "invite_token": "short-pw-token",
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert "8 characters" in r.text or "least 8" in r.text

    def test_register_admin_with_admin_token(self, client, db):
        """Using ADMIN_INVITE_TOKEN (set to 'admin-test-token-999' in conftest) creates admin."""
        from app.models import User as UserModel
        resp = client.get("/register")
        csrf = extract_csrf(resp.text)
        client.post(
            "/register",
            data={
                "username": "newadmin",
                "password": "adminpass1!",
                "invite_token": "admin-test-token-999",
                "csrf_token": csrf,
            },
            follow_redirects=False,
        )
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            user = s.query(UserModel).filter_by(username="newadmin").first()
            assert user is not None
            assert user.is_admin is True

    def test_register_missing_csrf_rejected(self, client, db):
        r = client.post(
            "/register",
            data={"username": "x", "password": "testpass1!", "invite_token": "tok"},
            follow_redirects=False,
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
class TestLogout:
    def test_logout_clears_session(self, auth_client):
        client, _ = auth_client
        # Verify we can access a protected page
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 200

        # Logout
        resp = client.get("/")
        csrf = extract_csrf(resp.text)
        client.post("/logout", data={"csrf_token": csrf}, follow_redirects=False)

        # After logout, protected page should redirect to login
        r2 = client.get("/", follow_redirects=False)
        assert r2.status_code == 303
        assert "/login" in r2.headers["location"]

    def test_logout_missing_csrf_rejected(self, auth_client):
        client, _ = auth_client
        r = client.post("/logout", data={}, follow_redirects=False)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Session fixation
# ---------------------------------------------------------------------------
class TestSessionFixation:
    def test_session_id_changes_on_login(self, client, db):
        """The session cookie value must change after successful login."""
        create_user(db)
        # Establish a pre-login session by visiting login page
        resp = client.get("/login")
        csrf = extract_csrf(resp.text)
        pre_login_cookie = client.cookies.get("session")

        client.post(
            "/login",
            data={"username": "testuser", "password": "testpass1!", "csrf_token": csrf},
            follow_redirects=False,
        )
        post_login_cookie = client.cookies.get("session")

        # Session cookie must have changed (old session cleared on login)
        assert pre_login_cookie != post_login_cookie
