"""Feed source registry. Each source is fetched independently (health-isolated)."""

from dataclasses import dataclass

from config import RSSHUB_BASE_URL


@dataclass(frozen=True)
class FeedSource:
    key: str
    url: str
    lang: str          # "en" | "zh"
    category: str      # default category hint; taxonomy may override per-item
    enabled: bool = True


FEED_SOURCES: list[FeedSource] = [
    FeedSource("cnbc_top",
               "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
               "en", "general"),
    FeedSource("marketwatch_top",
               "https://feeds.content.dowjones.io/public/rss/mw_topstories", "en", "general"),
    FeedSource("federal_reserve_monetary",
               "https://www.federalreserve.gov/feeds/press_monetary.xml", "en", "macro"),
    FeedSource("bls_cpi", "https://www.bls.gov/feed/cpi.rss", "en", "macro"),
    FeedSource("bls_employment", "https://www.bls.gov/feed/empsit.rss", "en", "macro"),
    FeedSource("bea_releases", "https://apps.bea.gov/rss/rss.xml", "en", "macro"),
    FeedSource("coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", "en", "crypto"),
    FeedSource("cointelegraph", "https://cointelegraph.com/rss", "en", "crypto"),
    FeedSource("jin10", f"{RSSHUB_BASE_URL}/jin10", "zh", "general"),
    FeedSource("wallstreetcn_live", f"{RSSHUB_BASE_URL}/wallstreetcn/live", "zh", "general"),
]


def enabled_sources() -> list[FeedSource]:
    return [s for s in FEED_SOURCES if s.enabled]
