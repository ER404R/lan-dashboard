"""Unit tests for app/steam.py — search_steam_games."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.steam import search_steam_games, STEAM_SEARCH_URL


class TestSearchSteamGames:
    """Tests for search_steam_games using mocked httpx responses."""

    def _make_mock_response(self, items):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"items": items}
        return mock_resp

    @pytest.mark.anyio
    async def test_returns_formatted_results(self):
        fake_items = [
            {"id": 570, "name": "Dota 2", "tiny_image": "https://example.com/dota.jpg"},
            {"id": 730, "name": "CS2", "tiny_image": "https://example.com/cs2.jpg"},
        ]
        mock_resp = self._make_mock_response(fake_items)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.steam.httpx.AsyncClient", return_value=mock_client):
            results = await search_steam_games("dota")

        assert len(results) == 2
        assert results[0]["appid"] == 570
        assert results[0]["name"] == "Dota 2"
        assert results[0]["thumbnail"] == "https://example.com/dota.jpg"
        assert results[0]["store_url"] == "https://store.steampowered.com/app/570"

    @pytest.mark.anyio
    async def test_respects_max_results(self):
        fake_items = [{"id": i, "name": f"Game {i}", "tiny_image": ""} for i in range(10)]
        mock_resp = self._make_mock_response(fake_items)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.steam.httpx.AsyncClient", return_value=mock_client):
            results = await search_steam_games("game", max_results=3)

        assert len(results) == 3

    @pytest.mark.anyio
    async def test_empty_items_returns_empty_list(self):
        mock_resp = self._make_mock_response([])

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.steam.httpx.AsyncClient", return_value=mock_client):
            results = await search_steam_games("nothing")

        assert results == []

    @pytest.mark.anyio
    async def test_missing_tiny_image_defaults_to_empty_string(self):
        fake_items = [{"id": 1, "name": "Game Without Image"}]
        mock_resp = self._make_mock_response(fake_items)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.steam.httpx.AsyncClient", return_value=mock_client):
            results = await search_steam_games("game")

        assert results[0]["thumbnail"] == ""

    @pytest.mark.anyio
    async def test_store_url_format(self):
        fake_items = [{"id": 12345, "name": "My Game", "tiny_image": ""}]
        mock_resp = self._make_mock_response(fake_items)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.steam.httpx.AsyncClient", return_value=mock_client):
            results = await search_steam_games("mygame")

        assert results[0]["store_url"] == "https://store.steampowered.com/app/12345"

    @pytest.mark.anyio
    async def test_default_max_results_is_five(self):
        fake_items = [{"id": i, "name": f"G{i}", "tiny_image": ""} for i in range(20)]
        mock_resp = self._make_mock_response(fake_items)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.steam.httpx.AsyncClient", return_value=mock_client):
            results = await search_steam_games("g")

        assert len(results) == 5

    @pytest.mark.anyio
    async def test_raises_on_http_error(self):
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404),
        ))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.steam.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await search_steam_games("error")
