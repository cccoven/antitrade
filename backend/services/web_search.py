"""Optional Tavily-backed web search for the AI assistant."""

from typing import Any

import httpx


def is_web_search_available() -> bool:
    from config import TAVILY_API_KEY

    return bool(TAVILY_API_KEY.strip())


def search_web(query: str, max_results: int = 5) -> dict[str, Any]:
    from config import TAVILY_API_KEY

    if not TAVILY_API_KEY.strip():
        return {"error": "web_search_not_configured", "results": []}

    capped = min(max(int(max_results or 5), 1), 8)
    try:
        with httpx.Client(timeout=15) as client:
            response = client.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {TAVILY_API_KEY}"},
                json={
                    "query": query,
                    "search_depth": "basic",
                    "max_results": capped,
                    "include_answer": False,
                    "include_raw_content": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return {"error": "web_search_unavailable", "results": []}

    results = []
    for item in payload.get("results", []):
        if not isinstance(item, dict):
            continue
        results.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "content": item.get("content"),
            "score": item.get("score"),
            "published_date": item.get("published_date"),
        })
    return {"query": payload.get("query", query), "results": results}
