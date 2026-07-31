from services.market_data import resolve_legacy_series_id
from services.market_gateway import (
    MarketDataGateway,
    default_catalog,
)


def test_legacy_tradingview_front_month_alias_resolves_to_canonical_series():
    gateway = MarketDataGateway(catalog=default_catalog())

    assert (
        resolve_legacy_series_id(gateway, "GC1!", "COMEX")
        == "series:futures:gc:front"
    )


def test_legacy_slashed_spot_alias_resolves_to_canonical_series():
    gateway = MarketDataGateway(catalog=default_catalog())

    assert (
        resolve_legacy_series_id(gateway, "EUR/USD")
        == "series:spot:eur-usd:consolidated"
    )


def test_legacy_new_overview_aliases_resolve_to_canonical_series():
    gateway = MarketDataGateway(catalog=default_catalog())

    assert (
        resolve_legacy_series_id(gateway, "AUD/USD")
        == "series:spot:aud-usd:consolidated"
    )
    assert (
        resolve_legacy_series_id(gateway, "SOL/USD")
        == "series:crypto:sol-usd:consolidated"
    )
