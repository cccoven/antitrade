def test_search_web_returns_compact_results(monkeypatch):
    import config
    from services import web_search

    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "query": "NQ futures",
                "results": [{
                    "title": "Market update",
                    "url": "https://example.com/market",
                    "content": "A concise market summary.",
                    "score": 0.9,
                    "published_date": "2026-07-15",
                    "raw_content": "must not leak",
                }],
            }

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def post(self, url, headers, json):
            captured.update({"url": url, "headers": headers, "json": json})
            return FakeResponse()

    monkeypatch.setattr(config, "TAVILY_API_KEY", "tvly-test")
    monkeypatch.setattr(web_search.httpx, "Client", lambda **_kwargs: FakeClient())

    result = web_search.search_web("NQ futures", max_results=99)

    assert captured["url"] == "https://api.tavily.com/search"
    assert captured["headers"]["Authorization"] == "Bearer tvly-test"
    assert captured["json"]["max_results"] == 8
    assert result["results"] == [{
        "title": "Market update",
        "url": "https://example.com/market",
        "content": "A concise market summary.",
        "score": 0.9,
        "published_date": "2026-07-15",
    }]


def test_search_web_reports_missing_configuration(monkeypatch):
    import config
    from services.web_search import search_web

    monkeypatch.setattr(config, "TAVILY_API_KEY", "")
    assert search_web("anything") == {
        "error": "web_search_not_configured",
        "results": [],
    }
