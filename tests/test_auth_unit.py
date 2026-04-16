"""Unit tests for app/auth.py — hash_password and verify_password."""

from app.auth import hash_password, verify_password


class TestHashPassword:
    def test_returns_string(self):
        h = hash_password("mypassword")
        assert isinstance(h, str)

    def test_hash_is_not_plaintext(self):
        h = hash_password("mypassword")
        assert "mypassword" not in h

    def test_two_hashes_of_same_password_differ(self):
        """bcrypt generates a unique salt each time."""
        h1 = hash_password("mypassword")
        h2 = hash_password("mypassword")
        assert h1 != h2

    def test_hash_starts_with_bcrypt_prefix(self):
        h = hash_password("mypassword")
        assert h.startswith("$2b$") or h.startswith("$2a$")

    def test_empty_string_can_be_hashed(self):
        h = hash_password("")
        assert len(h) > 0


class TestVerifyPassword:
    def test_correct_password_returns_true(self):
        h = hash_password("correct!")
        assert verify_password("correct!", h) is True

    def test_wrong_password_returns_false(self):
        h = hash_password("correct!")
        assert verify_password("wrong!", h) is False

    def test_empty_password_against_hash_of_empty(self):
        h = hash_password("")
        assert verify_password("", h) is True

    def test_empty_password_against_non_empty_hash(self):
        h = hash_password("notempty")
        assert verify_password("", h) is False

    def test_case_sensitive(self):
        h = hash_password("Password1!")
        assert verify_password("password1!", h) is False
        assert verify_password("PASSWORD1!", h) is False
        assert verify_password("Password1!", h) is True

    def test_round_trip_various_passwords(self):
        passwords = ["simple", "w1th_numb3rs", "!@#$%^&*()", "unicode_\u00e9\u00e0\u00fc"]
        for pw in passwords:
            h = hash_password(pw)
            assert verify_password(pw, h) is True, f"round-trip failed for: {pw!r}"
