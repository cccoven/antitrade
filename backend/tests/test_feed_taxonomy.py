import pytest

from services.feed_taxonomy import classify
from services.market_gateway import InstrumentSearch, default_catalog


def test_btc_maps_to_crypto_and_symbol():
    cat, syms = classify("Bitcoin surges past 70k", "BTC breaks resistance")
    assert cat == "crypto"
    assert "instrument:crypto:btc-usd" in syms


def test_gold_maps_to_symbol():
    cat, syms = classify("Gold hits record high", "XAU demand rises")
    assert "instrument:spot:xau-usd" in syms


def test_fed_maps_to_macro():
    cat, syms = classify("Fed holds rates steady", "FOMC decision on CPI")
    assert cat == "macro"


def test_unknown_defaults_to_general_no_symbols():
    cat, syms = classify("Company X announces new CEO", "corporate news")
    assert cat == "general"
    assert syms == []


def test_chinese_keywords():
    cat, syms = classify("黄金创新高", "美联储加息预期")
    assert "instrument:spot:xau-usd" in syms
    assert cat == "macro"


def test_common_words_do_not_false_match():
    cat, syms = classify("Market turmoil as European banks slide", "Goldman warns")
    assert "instrument:commodity:wti" not in syms  # 'oil' in 'turmoil'
    assert "instrument:spot:eur-usd" not in syms   # 'euro' in 'European'
    assert "instrument:spot:xau-usd" not in syms   # 'gold' in 'Goldman'


@pytest.mark.parametrize(
    ("title", "expected_id"),
    [
        ("Bitcoin update", "instrument:crypto:btc-usd"),
        ("Ethereum update", "instrument:crypto:eth-usd"),
        ("Gold update", "instrument:spot:xau-usd"),
        ("Silver update", "instrument:spot:xag-usd"),
        ("WTI crude update", "instrument:commodity:wti"),
        ("EUR/USD update", "instrument:spot:eur-usd"),
        ("USD/JPY update", "instrument:spot:usd-jpy"),
        ("Nasdaq NDX update", "instrument:index:ndx"),
        ("S&P 500 update", "instrument:index:spx500"),
    ],
)
def test_every_taxonomy_tag_resolves_through_canonical_catalog(title, expected_id):
    _, symbols = classify(title, "")
    assert expected_id in symbols
    instrument = default_catalog().resolve_instrument(
        InstrumentSearch(text=expected_id),
    )
    assert instrument is not None
    assert instrument.id == expected_id
