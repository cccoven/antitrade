# AntiTrade

AntiTrade is a trading research and journaling product. This glossary defines the market-identity language shared by its analysis, replay, backtest, journal, and market-overview features.

## Market identity

**Instrument**:
The economic or contractual object being quoted or traded, such as Apple common stock, the XAU/USD spot pair, or a specific September NQ futures contract.
_Avoid_: Symbol, ticker, market

**Venue**:
The canonical trading or quoting venue associated with a listing, preferably identified by a standard market identifier rather than a provider-specific exchange name.
_Avoid_: Provider exchange, market

**Listing**:
A venue-specific manifestation of an Instrument, such as BTC/USD on Coinbase or Apple common stock on Nasdaq.
_Avoid_: Symbol, ticker

**Market Series**:
The exact price history requested by a feature. It may represent a Listing directly or a derived series such as a continuous futures contract.
_Avoid_: Instrument when referring to synthetic or aggregated data

**Spot Pair**:
A quoted relationship between a base asset and a quote asset, such as XAU/USD or EUR/USD.
_Avoid_: Futures contract, commodity ticker

**Futures Product**:
A family of futures contracts sharing an underlying and contract specification, such as GC or NQ.
_Avoid_: Futures contract, continuous contract

**Futures Contract**:
A dated, tradeable member of a Futures Product with a defined expiry.
_Avoid_: Root symbol, continuous contract

**Continuous Futures Series**:
A synthetic Market Series formed by rolling across multiple Futures Contracts according to an explicit roll and adjustment policy. It is not itself a tradeable Instrument.
_Avoid_: Futures contract

## Provider identity

**Market Data Provider**:
An external source that supplies quotes, candles, or reference data, such as Twelve Data, Yahoo, TradingView, or Databento.
_Avoid_: Exchange, venue

**Provider Symbol**:
A Market Data Provider's identifier for an Instrument, Listing, or Market Series, such as `GC=F`, `GC1!`, or `XAU/USD`.
_Avoid_: Canonical symbol, Instrument ID

**Alias**:
A human or legacy input that may resolve to one or more Instruments or Market Series when combined with context such as asset class and Venue.
_Avoid_: Instrument ID

## Market data

**Candle Series**:
An ordered sequence of normalized OHLCV bars for one Market Series, timeframe, adjustment policy, and source provenance.
_Avoid_: Raw provider response

**Quote Snapshot**:
A point-in-time normalized market quote with its source and observation time.
_Avoid_: Candle Series

## Automation

**Automation**:
The product area for scheduled monitoring, reporting, and risk-alert workflows.
_Avoid_: Agent Center

**Automation Task**:
A user-configured unit of automated work with a type, schedule, scope, and notification policy.
_Avoid_: Agent

**Analysis Instruction**:
An optional user preference that changes the focus and presentation of an Automation Task's report without changing its trigger, permissions, or notification policy.
_Avoid_: Prompt, rule, trigger

**Run**:
A single execution of an Automation Task.
_Avoid_: Task

**Finding**:
An actionable observation produced by an Automation Task.
_Avoid_: Run, notification

**Report**:
A time-bounded summary produced by an Automation Task.
_Avoid_: Finding, notification

**Agent**:
An autonomous actor with a persistent role, tools, and the ability to perform multiple tasks; it is not an Automation Task.
_Avoid_: Automation Task
