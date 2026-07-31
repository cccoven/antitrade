from services.feed_sources import FEED_SOURCES, enabled_sources, FeedSource


def test_sources_have_unique_keys():
    keys = [s.key for s in FEED_SOURCES]
    assert len(keys) == len(set(keys))


def test_each_source_wellformed():
    for s in FEED_SOURCES:
        assert isinstance(s, FeedSource)
        assert s.url.startswith("http")
        assert s.lang in ("en", "zh")
        assert s.category in ("general", "crypto", "forex", "macro")


def test_enabled_sources_filters_disabled():
    enabled = enabled_sources()
    assert all(s.enabled for s in enabled)
    assert len(enabled) >= 1
