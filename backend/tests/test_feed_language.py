from services.feed_language import (
    briefing_content_matches_language,
    detect_feed_language,
)


def test_detect_feed_language_uses_reader_facing_content():
    assert detect_feed_language("美联储维持利率不变", fallback="en") == "zh"
    assert detect_feed_language("Fed keeps rates unchanged", fallback="zh") == "en"


def test_detect_feed_language_handles_tickers_and_ambiguous_titles():
    assert detect_feed_language("BTC暴涨", "市场风险偏好回升", "en") == "zh"
    assert detect_feed_language("SPY 742.90", fallback="en") == "en"


def test_briefing_language_check_rejects_wrong_script():
    chinese_content = {
        "hot": [{"title": "美联储维持利率不变"}],
        "sections": [{"category": "macro", "points": [{"text": "市场等待发布会"}]}],
    }
    english_content = {
        "hot": [{"title": "Fed keeps rates unchanged"}],
        "sections": [{"category": "macro", "points": [{"text": "Markets await guidance"}]}],
    }

    assert briefing_content_matches_language(chinese_content, "zh")
    assert not briefing_content_matches_language(chinese_content, "en")
    assert briefing_content_matches_language(english_content, "en")
    assert not briefing_content_matches_language(english_content, "zh")
