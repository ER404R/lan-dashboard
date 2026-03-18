"""Tests for the feature-request routes."""
import pytest

from tests.conftest import create_user, extract_csrf


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _create_feature(client, title="My Feature", description="A detailed description"):
    """POST a new feature request and return the response."""
    resp = client.get("/features/new")
    csrf = extract_csrf(resp.text)
    return client.post(
        "/features",
        data={"title": title, "description": description, "csrf_token": csrf},
        follow_redirects=False,
    )


# ---------------------------------------------------------------------------
# Creating feature requests
# ---------------------------------------------------------------------------
class TestCreateFeature:
    def test_create_feature_request(self, auth_client, db):
        client, user = auth_client
        r = _create_feature(client)
        assert r.status_code == 303
        assert r.headers["location"] == "/features"
        r2 = client.get("/features")
        assert "My Feature" in r2.text

    def test_feature_description_too_long(self, auth_client, db):
        client, user = auth_client
        resp = client.get("/features/new")
        csrf = extract_csrf(resp.text)
        r = client.post(
            "/features",
            data={
                "title": "Short title",
                "description": "X" * 2001,
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )
        assert "2000" in r.text or "at most" in r.text

    def test_create_feature_missing_csrf(self, auth_client, db):
        client, _ = auth_client
        r = client.post(
            "/features",
            data={"title": "T", "description": "D"},
            follow_redirects=False,
        )
        assert r.status_code == 403

    def test_create_feature_unauthenticated(self, client):
        r = client.get("/features/new", follow_redirects=False)
        assert r.status_code == 303
        assert "/login" in r.headers["location"]

    def test_max_open_requests_enforced(self, auth_client, db):
        """4th open request should be blocked (max is 3)."""
        client, user = auth_client
        for i in range(3):
            r = _create_feature(client, title=f"Feature {i}")
            assert r.status_code == 303, f"Feature {i} creation failed"
        r = _create_feature(client, title="One too many")
        assert r.status_code == 303
        r2 = client.get("/features", follow_redirects=True)
        assert "3" in r2.text or "open" in r2.text.lower()


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
class TestComments:
    def _get_feature_id(self, db):
        from app.models import FeatureRequest
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            feat = s.query(FeatureRequest).first()
            return feat.id if feat else None

    def test_comment_on_feature(self, auth_client, db):
        client, user = auth_client
        _create_feature(client)
        fid = self._get_feature_id(db)
        resp = client.get(f"/features/{fid}")
        csrf = extract_csrf(resp.text)
        r = client.post(
            f"/features/{fid}/comment",
            data={"content": "Great idea!", "csrf_token": csrf},
            follow_redirects=True,
        )
        assert "Great idea!" in r.text

    def test_comment_too_long(self, auth_client, db):
        client, user = auth_client
        _create_feature(client)
        fid = self._get_feature_id(db)
        resp = client.get(f"/features/{fid}")
        csrf = extract_csrf(resp.text)
        r = client.post(
            f"/features/{fid}/comment",
            data={"content": "Y" * 1001, "csrf_token": csrf},
            follow_redirects=True,
        )
        assert "1000" in r.text or "at most" in r.text

    def test_comment_missing_csrf(self, auth_client, db):
        client, user = auth_client
        _create_feature(client)
        fid = self._get_feature_id(db)
        r = client.post(
            f"/features/{fid}/comment",
            data={"content": "No token"},
            follow_redirects=False,
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Admin-only actions: resolve and delete
# ---------------------------------------------------------------------------
class TestAdminActions:
    def _setup_feature(self, client):
        _create_feature(client, title="Admin target")
        from app.models import FeatureRequest
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            return s.query(FeatureRequest).first().id

    def test_resolve_feature_blocks_regular_user(self, auth_client, db):
        client, user = auth_client
        fid = self._setup_feature(client)
        resp = client.get(f"/features/{fid}")
        csrf = extract_csrf(resp.text)
        r = client.post(
            f"/features/{fid}/resolve",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        from app.models import FeatureRequest
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            feat = s.get(FeatureRequest, fid)
            assert feat.resolved is False

    def test_resolve_feature_succeeds_for_admin(self, admin_client, db):
        client, admin = admin_client
        fid = self._setup_feature(client)
        resp = client.get(f"/features/{fid}")
        csrf = extract_csrf(resp.text)
        r = client.post(
            f"/features/{fid}/resolve",
            data={"csrf_token": csrf},
            follow_redirects=True,
        )
        assert "resolved" in r.text.lower() or "Resolved" in r.text
        from app.models import FeatureRequest
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            feat = s.get(FeatureRequest, fid)
            assert feat.resolved is True

    def test_delete_feature_blocks_regular_user(self, auth_client, db):
        client, user = auth_client
        fid = self._setup_feature(client)
        resp = client.get(f"/features/{fid}")
        csrf = extract_csrf(resp.text)
        r = client.post(
            f"/features/{fid}/delete",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        from app.models import FeatureRequest
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            assert s.get(FeatureRequest, fid) is not None

    def test_delete_feature_succeeds_for_admin(self, admin_client, db):
        client, admin = admin_client
        fid = self._setup_feature(client)
        resp = client.get(f"/features/{fid}")
        csrf = extract_csrf(resp.text)
        r = client.post(
            f"/features/{fid}/delete",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert r.status_code == 303
        from app.models import FeatureRequest
        from tests.conftest import _TestingSession
        with _TestingSession() as s:
            assert s.get(FeatureRequest, fid) is None
