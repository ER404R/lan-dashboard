import httpx

STEAM_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"


async def search_steam_games(query: str, max_results: int = 5) -> list[dict]:
    """Search Steam store for games matching the query."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            STEAM_SEARCH_URL,
            params={"term": query, "l": "english", "cc": "US"},
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])[:max_results]
        return [
            {
                "appid": item["id"],
                "name": item["name"],
                "thumbnail": item.get("tiny_image", ""),
                "store_url": f"https://store.steampowered.com/app/{item['id']}",
            }
            for item in items
        ]
