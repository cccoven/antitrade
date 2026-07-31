import logging
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pandas as pd
import talib
from providers import LLMProvider
from i18n import t
from services.market_data import resolve_legacy_series_id
from services.market_data_runtime import get_market_data_gateway
from services.market_gateway import CandleQuery, MarketDataError

logger = logging.getLogger(__name__)

@dataclass
class AnalysisCacheEntry:
    analysis: str
    analyzed_at: str


@dataclass
class AnalysisJobEntry:
    job_id: str
    exchange: str
    symbol: str
    interval: str
    lang: str
    status: str
    created_at: str
    updated_at: str
    analysis: str | None = None
    analyzed_at: str | None = None
    error: str | None = None


_analysis_cache: dict[tuple[str, str, str], AnalysisCacheEntry] = {}
_analysis_jobs: dict[str, AnalysisJobEntry] = {}
_running_jobs_by_key: dict[tuple[str, str, str], str] = {}


def fetch_ohlcv(symbol: str, exchange: str, interval: str, n_bars: int = 200) -> pd.DataFrame | None:
    duration = {
        "1": timedelta(minutes=1),
        "5": timedelta(minutes=5),
        "15": timedelta(minutes=15),
        "60": timedelta(hours=1),
        "240": timedelta(hours=4),
        "D": timedelta(days=1),
        "W": timedelta(weeks=1),
        "M": timedelta(days=31),
    }.get(interval)
    if duration is None:
        logger.error(f"Unsupported interval: {interval}")
        return None
    gateway = get_market_data_gateway()
    series_id = resolve_legacy_series_id(gateway, symbol, exchange)
    if not series_id:
        logger.error("Unknown or ambiguous market symbol: %s", symbol)
        return None
    end = _now()
    try:
        series = gateway.get_candles(
            CandleQuery(
                series_id=series_id,
                timeframe=interval,
                start=end - duration * max(n_bars, 1) * 3,
                end=end,
                purpose="interactive",
            ),
        )
    except MarketDataError as exc:
        logger.error("Failed to fetch %s: %s", symbol, exc.code)
        return None
    candles = series.candles[-max(n_bars, 1):]
    return pd.DataFrame(
        {
            "open": [candle.open for candle in candles],
            "high": [candle.high for candle in candles],
            "low": [candle.low for candle in candles],
            "close": [candle.close for candle in candles],
            "volume": [candle.volume for candle in candles],
        },
        index=pd.DatetimeIndex([candle.open_time for candle in candles]),
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values

    df['ema50'] = talib.EMA(close, timeperiod=50)
    df['ema144'] = talib.EMA(close, timeperiod=144)
    df['ema169'] = talib.EMA(close, timeperiod=169)
    df['sma20'] = talib.SMA(close, timeperiod=20)
    df['atr14'] = talib.ATR(high, low, close, timeperiod=14)

    upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2)
    df['bb_upper'] = upper
    df['bb_middle'] = middle
    df['bb_lower'] = lower

    df['rsi14'] = talib.RSI(close, timeperiod=14)

    macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
    df['macd'] = macd
    df['macd_signal'] = macd_signal
    df['macd_hist'] = macd_hist

    return df


def build_analysis_prompt(df: pd.DataFrame, symbol: str, exchange: str, interval: str, lang: str = "zh") -> str:
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    change_pct = (latest['close'] - prev['close']) / prev['close'] * 100

    indicators = []
    indicators.append(t("prompt.current_price", lang, value=f"{latest['close']:.4f}", change=f"{change_pct:+.2f}%"))
    indicators.append(t("prompt.ohlc", lang, open=f"{latest['open']:.4f}", high=f"{latest['high']:.4f}", low=f"{latest['low']:.4f}", close=f"{latest['close']:.4f}"))

    for name, key in [("EMA50", "ema50"), ("EMA144", "ema144"), ("EMA169", "ema169"), ("SMA20", "sma20")]:
        val = latest.get(key)
        if pd.notna(val):
            dist = latest['close'] - val
            indicators.append(t("prompt.price_deviation", lang, name=name, value=f"{val:.4f}", dist=f"{dist:+.4f}"))

    if pd.notna(latest.get('atr14')):
        indicators.append(f"ATR(14): {latest['atr14']:.4f}")

    if pd.notna(latest.get('bb_upper')) and pd.notna(latest.get('bb_lower')):
        bb_width = latest['bb_upper'] - latest['bb_lower']
        bb_pos = (latest['close'] - latest['bb_lower']) / bb_width * 100 if bb_width > 0 else 50
        indicators.append(t("prompt.bb", lang, upper=f"{latest['bb_upper']:.4f}", lower=f"{latest['bb_lower']:.4f}", position=f"{bb_pos:.1f}"))

    if pd.notna(latest.get('rsi14')):
        indicators.append(f"RSI(14): {latest['rsi14']:.1f}")

    if pd.notna(latest.get('macd')):
        indicators.append(f"MACD: {latest['macd']:.4f} Signal: {latest['macd_signal']:.4f} Hist: {latest['macd_hist']:.4f}")

    indicators.append(t("prompt.high_n", lang, value=f"{df['high'].tail(20).max():.4f}"))
    indicators.append(t("prompt.low_n", lang, value=f"{df['low'].tail(20).min():.4f}"))

    indicator_text = "\n".join(indicators)

    recent = df.tail(30)
    klines = [t("prompt.kline_header", lang)]
    for idx, row in recent.iterrows():
        ts = idx.strftime("%m-%d %H:%M") if hasattr(idx, 'strftime') else str(idx)
        klines.append(f"{ts}  {row['open']:>9.2f} {row['high']:>9.2f} {row['low']:>9.2f} {row['close']:>9.2f} {row['volume']:>10.0f}")
    kline_text = "\n".join(klines)

    interval_name = t(f"interval.{interval}", lang)

    return f"""{t("prompt.system", lang, exchange=exchange, symbol=symbol, interval=interval_name)}

## {t("prompt.section_indicators", lang)}
{indicator_text}

## {t("prompt.section_klines", lang)}
{kline_text}

## {t("prompt.section_analyze", lang)}

1. {t("prompt.item_trend", lang)}
2. {t("prompt.item_support_resistance", lang)}
3. {t("prompt.item_momentum", lang)}
4. {t("prompt.item_risk", lang)}
5. {t("prompt.item_suggestion", lang)}

{t("prompt.response_instruction", lang)}"""


def create_provider() -> LLMProvider:
    """Factory: create LLM provider based on config."""
    from config import LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

    if LLM_PROVIDER == "demo":
        from providers.demo_provider import DemoProvider
        return DemoProvider()
    elif LLM_PROVIDER == "openai":
        from providers.openai_provider import OpenAIProvider
        return OpenAIProvider(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, model=LLM_MODEL)
    elif LLM_PROVIDER == "anthropic":
        from providers.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=LLM_API_KEY, model=LLM_MODEL)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}")


def get_analysis_cache_key(symbol: str, exchange: str, interval: str) -> tuple[str, str, str]:
    return (exchange, symbol, interval)


def get_latest_analysis(symbol: str, exchange: str, interval: str) -> AnalysisCacheEntry | None:
    return _analysis_cache.get(get_analysis_cache_key(symbol, exchange, interval))


def get_analysis_job(job_id: str) -> AnalysisJobEntry | None:
    return _analysis_jobs.get(job_id)


def create_analysis_job(symbol: str, exchange: str, interval: str, lang: str = "zh", force_refresh: bool = False) -> AnalysisJobEntry:
    cache_key = get_analysis_cache_key(symbol, exchange, interval)
    running_job_id = _running_jobs_by_key.get(cache_key)
    if running_job_id:
        running_job = _analysis_jobs.get(running_job_id)
        if running_job and running_job.status in {"queued", "running"}:
            return running_job

    now = datetime.now(timezone.utc).isoformat()
    job = AnalysisJobEntry(
        job_id=str(uuid4()),
        exchange=exchange,
        symbol=symbol,
        interval=interval,
        lang=lang,
        status="queued",
        created_at=now,
        updated_at=now,
    )
    _analysis_jobs[job.job_id] = job
    _running_jobs_by_key[cache_key] = job.job_id
    asyncio.create_task(_run_analysis_job(job.job_id, force_refresh=force_refresh))
    return job


async def _run_analysis_job(job_id: str, force_refresh: bool = False) -> None:
    job = _analysis_jobs.get(job_id)
    if not job:
        return

    cache_key = get_analysis_cache_key(job.symbol, job.exchange, job.interval)
    job.status = "running"
    job.updated_at = datetime.now(timezone.utc).isoformat()

    try:
        analysis, analyzed_at = await analyze_symbol(
            symbol=job.symbol,
            exchange=job.exchange,
            interval=job.interval,
            lang=job.lang,
            force_refresh=force_refresh,
        )
        job.status = "completed"
        job.analysis = analysis
        job.analyzed_at = analyzed_at
        job.updated_at = datetime.now(timezone.utc).isoformat()
        job.error = None
    except Exception as exc:
        logger.exception("Analysis job failed", exc_info=exc)
        job.status = "failed"
        job.error = t("error.analysis_unavailable", job.lang)
        job.updated_at = datetime.now(timezone.utc).isoformat()
    finally:
        if _running_jobs_by_key.get(cache_key) == job_id:
            _running_jobs_by_key.pop(cache_key, None)


async def analyze_symbol(
    symbol: str,
    exchange: str,
    interval: str,
    lang: str = "zh",
    force_refresh: bool = False,
) -> tuple[str, str]:
    cache_key = get_analysis_cache_key(symbol, exchange, interval)
    cached = _analysis_cache.get(cache_key)
    if cached is not None and not force_refresh:
        return cached.analysis, cached.analyzed_at

    provider = create_provider()
    if provider.__class__.__name__ == "DemoProvider":
        analysis = await provider.complete(
            t("prompt.demo", lang, exchange=exchange, symbol=symbol, interval=t(f"interval.{interval}", lang))
        )
        analyzed_at = datetime.now(timezone.utc).isoformat()
        _analysis_cache[cache_key] = AnalysisCacheEntry(
            analysis=analysis,
            analyzed_at=analyzed_at,
        )
        return analysis, analyzed_at

    # Fetch data
    df = fetch_ohlcv(symbol, exchange, interval)
    if df is None or df.empty:
        error_msg = t("error.fetch_failed", lang, symbol=f"{exchange}:{symbol}")
        return error_msg, datetime.now(timezone.utc).isoformat()

    # Calculate indicators
    df = calculate_indicators(df)

    # Build prompt
    prompt = build_analysis_prompt(df, symbol, exchange, interval, lang=lang)

    # Call LLM via provider
    try:
        analysis = await provider.complete(prompt)
        analyzed_at = datetime.now(timezone.utc).isoformat()
        _analysis_cache[cache_key] = AnalysisCacheEntry(
            analysis=analysis,
            analyzed_at=analyzed_at,
        )
        return analysis, analyzed_at
    except Exception as e:
        logger.error(f"LLM provider failed: {e}")
        error_msg = t("error.analysis_unavailable_md", lang)
        return error_msg, datetime.now(timezone.utc).isoformat()
