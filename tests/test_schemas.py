"""Unit tests for Pydantic form schemas (app/schemas.py)."""
import pytest
from pydantic import ValidationError

from app.schemas import AddGameForm, LoginForm, RateForm, RegisterForm


class TestLoginForm:
    def test_valid_login(self):
        f = LoginForm(username="alice", password="secret")
        assert f.username == "alice"
        assert f.password == "secret"

    def test_empty_username_rejected(self):
        with pytest.raises(ValidationError):
            LoginForm(username="", password="secret")

    def test_username_too_long_rejected(self):
        with pytest.raises(ValidationError):
            LoginForm(username="a" * 51, password="secret")

    def test_empty_password_rejected(self):
        with pytest.raises(ValidationError):
            LoginForm(username="alice", password="")

    def test_username_max_length_accepted(self):
        f = LoginForm(username="a" * 50, password="pass")
        assert len(f.username) == 50


class TestRegisterForm:
    def test_valid_register(self):
        f = RegisterForm(username="bob", password="strongpass1", invite_token="tok")
        assert f.username == "bob"

    def test_username_too_short_rejected(self):
        with pytest.raises(ValidationError):
            RegisterForm(username="ab", password="strongpass1", invite_token="tok")

    def test_username_min_length_accepted(self):
        f = RegisterForm(username="abc", password="strongpass1", invite_token="tok")
        assert f.username == "abc"

    def test_username_too_long_rejected(self):
        with pytest.raises(ValidationError):
            RegisterForm(username="a" * 51, password="strongpass1", invite_token="tok")

    def test_password_too_short_rejected(self):
        with pytest.raises(ValidationError):
            RegisterForm(username="alice", password="short12", invite_token="tok")

    def test_password_min_length_accepted(self):
        f = RegisterForm(username="alice", password="exactly8", invite_token="tok")
        assert len(f.password) == 8

    def test_empty_invite_token_rejected(self):
        with pytest.raises(ValidationError):
            RegisterForm(username="alice", password="strongpass1", invite_token="")


class TestRateForm:
    def test_valid_rating_zero(self):
        f = RateForm(value=0)
        assert f.value == 0

    def test_valid_rating_ten(self):
        f = RateForm(value=10)
        assert f.value == 10

    def test_valid_rating_midrange(self):
        f = RateForm(value=5)
        assert f.value == 5

    def test_rating_above_ten_rejected(self):
        with pytest.raises(ValidationError):
            RateForm(value=11)

    def test_rating_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            RateForm(value=-1)


class TestAddGameForm:
    def test_valid_game_form(self):
        f = AddGameForm(
            steam_appid=123456,
            name="Half-Life 3",
            thumbnail_url="https://example.com/img.jpg",
            steam_url="https://store.steampowered.com/app/123456",
        )
        assert f.steam_appid == 123456
        assert f.name == "Half-Life 3"

    def test_defaults_for_optional_fields(self):
        f = AddGameForm(steam_appid=1, name="Game")
        assert f.thumbnail_url == ""
        assert f.steam_url == ""

    def test_missing_steam_appid_rejected(self):
        with pytest.raises(ValidationError):
            AddGameForm(name="Game")

    def test_missing_name_rejected(self):
        with pytest.raises(ValidationError):
            AddGameForm(steam_appid=123)
