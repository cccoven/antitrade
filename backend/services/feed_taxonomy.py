"""Rule-based classification + symbol tagging for feed items (zero LLM cost)."""

import re

# keyword (lowercased) -> canonical Instrument ID
_SYMBOL_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("bitcoin", "btc", "比特币"), "instrument:crypto:btc-usd"),
    (("ethereum", "eth", "以太"), "instrument:crypto:eth-usd"),
    (("gold", "xau", "黄金"), "instrument:spot:xau-usd"),
    (("silver", "xag", "白银"), "instrument:spot:xag-usd"),
    (("crude", "oil", "wti", "原油"), "instrument:commodity:wti"),
    (("eur/usd", "eurusd", "euro", "欧元"), "instrument:spot:eur-usd"),
    (("usd/jpy", "usdjpy", "yen", "日元"), "instrument:spot:usd-jpy"),
    (("nasdaq", "ndx", "纳斯达克"), "instrument:index:ndx"),
    (("s&p", "sp500", "spx", "标普"), "instrument:index:spx500"),
]

# category -> keywords (lowercased). First match wins in this order.
_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("macro", ("fed", "fomc", "cpi", "inflation", "interest rate", "nonfarm", "nfp", "gdp",
               "美联储", "加息", "降息", "通胀", "非农", "利率")),
    ("crypto", ("bitcoin", "btc", "ethereum", "eth", "crypto", "token", "比特币", "以太", "加密")),
    ("forex", ("eur/usd", "usd/jpy", "forex", "dollar", "yen", "euro", "外汇", "美元", "欧元", "日元")),
]


def _haystack(title: str, summary: str) -> str:
    return f"{title or ''} {summary or ''}".lower()


def _matches(keyword: str, text: str) -> bool:
    # CJK keywords have no word boundaries — plain substring match.
    if any("一" <= ch <= "鿿" for ch in keyword):
        return keyword in text
    # ASCII keywords: word-boundary match to avoid 'oil' in 'turmoil', etc.
    # Escape so tokens like 's&p', 'eur/usd', 'usd/jpy' are treated literally;
    # use lookarounds instead of \b because \b doesn't fire next to '&' or '/'.
    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text) is not None


def classify(title: str, summary: str) -> tuple[str, list[str]]:
    """Return (category, symbols). category defaults to 'general'."""
    text = _haystack(title, summary)

    symbols: list[str] = []
    for keywords, symbol in _SYMBOL_KEYWORDS:
        if any(_matches(kw, text) for kw in keywords) and symbol not in symbols:
            symbols.append(symbol)

    category = "general"
    for cat, keywords in _CATEGORY_KEYWORDS:
        if any(_matches(kw, text) for kw in keywords):
            category = cat
            break

    return category, symbols
