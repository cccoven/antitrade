from services.market_gateway import InstrumentSearch

INTERVAL_SECONDS = {
    "1": 60,
    "5": 5 * 60,
    "15": 15 * 60,
    "60": 60 * 60,
    "240": 4 * 60 * 60,
    "D": 24 * 60 * 60,
    "W": 7 * 24 * 60 * 60,
    "M": 30 * 24 * 60 * 60,
}


def resolve_legacy_series_id(
    gateway,
    symbol: str,
    exchange: str = "",
) -> str | None:
    asset_class = _legacy_asset_class(symbol)
    if asset_class is None:
        return None
    venue = _legacy_venue(asset_class, exchange)
    matches = gateway.search_instruments(
        InstrumentSearch(
            text=symbol,
            asset_class=asset_class,
            venue=venue,
        ),
    )
    if len(matches) != 1:
        consolidated = [
            match
            for match in matches
            if match.series_kind == "consolidated"
        ]
        if len(consolidated) == 1:
            matches = consolidated
    if len(matches) != 1:
        return None
    return matches[0].series_id


def _legacy_asset_class(symbol: str) -> str | None:
    normalized = symbol.strip().upper().replace(" ", "")
    compact = normalized.replace("/", "")
    if normalized in {"NQ", "MNQ", "ES", "MES", "GC", "MGC"} or normalized.endswith("1!"):
        return "futures"
    if compact in {
        "XAUUSD", "XAGUSD", "EURUSD", "GBPUSD",
        "USDJPY", "AUDUSD", "USDCAD", "USDCHF",
    }:
        return "spot"
    if compact in {"BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD"}:
        return "crypto"
    if normalized in {
        "AAPL", "TSLA", "SPY", "QQQ", "IWM", "DIA",
        "TLT", "HYG", "USO", "GLD", "SLV",
    }:
        return "equity"
    if normalized == "SPX500":
        return "index"
    return None


def _legacy_venue(asset_class: str, exchange: str) -> str | None:
    normalized = exchange.strip().upper() if exchange else ""
    if asset_class == "crypto" and normalized in {"BINANCE", "COINBASE"}:
        return normalized
    if asset_class == "futures" and normalized in {"COMEX", "CME_MINI"}:
        return normalized
    if asset_class == "equity":
        return {
            "NASDAQ": "XNAS",
            "XNAS": "XNAS",
            "AMEX": "ARCX",
            "ARCX": "ARCX",
        }.get(normalized)
    return None
