"""Unit tests for ORM model properties (app/models.py)."""

from app.models import InviteToken


class TestInviteTokenIsAvailable:
    """Tests for InviteToken.is_available property."""

    def _make_token(self, **kwargs):
        defaults = {"token": "tok-" + str(id(kwargs)), "max_uses": 1, "use_count": 0, "revoked": False}
        defaults.update(kwargs)
        return InviteToken(**defaults)

    def test_available_fresh_token(self, db):
        t = self._make_token(token="fresh-1", max_uses=1, use_count=0)
        db.add(t)
        db.commit()
        assert t.is_available is True

    def test_not_available_when_revoked(self, db):
        t = self._make_token(token="revoked-1", max_uses=5, use_count=0, revoked=True)
        db.add(t)
        db.commit()
        assert t.is_available is False

    def test_not_available_when_exhausted(self, db):
        t = self._make_token(token="exhausted-1", max_uses=1, use_count=1)
        db.add(t)
        db.commit()
        assert t.is_available is False

    def test_available_unlimited_token(self, db):
        """max_uses=0 means unlimited — always available while not revoked."""
        t = self._make_token(token="unlimited-1", max_uses=0, use_count=999)
        db.add(t)
        db.commit()
        assert t.is_available is True

    def test_unlimited_but_revoked_is_unavailable(self, db):
        t = self._make_token(token="unlimited-revoked-1", max_uses=0, use_count=0, revoked=True)
        db.add(t)
        db.commit()
        assert t.is_available is False

    def test_partially_used_still_available(self, db):
        t = self._make_token(token="partial-1", max_uses=5, use_count=3)
        db.add(t)
        db.commit()
        assert t.is_available is True

    def test_exactly_at_limit_unavailable(self, db):
        t = self._make_token(token="at-limit-1", max_uses=3, use_count=3)
        db.add(t)
        db.commit()
        assert t.is_available is False


class TestInviteTokenStatusLabel:
    """Tests for InviteToken.status_label property."""

    def _make_token(self, **kwargs):
        defaults = {"token": "stl-" + str(id(kwargs)), "max_uses": 1, "use_count": 0, "revoked": False}
        defaults.update(kwargs)
        return InviteToken(**defaults)

    def test_label_available(self, db):
        t = self._make_token(token="label-avail-1", max_uses=1, use_count=0)
        db.add(t)
        db.commit()
        assert t.status_label == "Available"

    def test_label_revoked(self, db):
        t = self._make_token(token="label-rev-1", revoked=True)
        db.add(t)
        db.commit()
        assert t.status_label == "Revoked"

    def test_label_exhausted(self, db):
        t = self._make_token(token="label-exh-1", max_uses=2, use_count=2)
        db.add(t)
        db.commit()
        assert t.status_label == "Exhausted"

    def test_label_unlimited_available(self, db):
        """max_uses=0 means unlimited: should be Available, not Exhausted."""
        t = self._make_token(token="label-unl-1", max_uses=0, use_count=100)
        db.add(t)
        db.commit()
        assert t.status_label == "Available"

    def test_label_revoked_takes_precedence_over_exhausted(self, db):
        """Revoked check happens first, so a revoked exhausted token is 'Revoked'."""
        t = self._make_token(token="label-rev-exh-1", max_uses=1, use_count=1, revoked=True)
        db.add(t)
        db.commit()
        assert t.status_label == "Revoked"
