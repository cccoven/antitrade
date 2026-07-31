"""SQLAlchemy ORM models — faithful 1:1 map of the legacy SQLite schema."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer,
    JSON, String, Text, UniqueConstraint, column,
)
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String, nullable=False)
    password_set: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    name: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    auth_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class UserOAuthIdentity(Base):
    __tablename__ = "user_oauth_identities"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_user_oauth_provider_subject"),
        UniqueConstraint("user_id", "provider", name="uq_user_oauth_user_provider"),
        Index("idx_user_oauth_identities_user", "user_id"),
    )


class UserMfaFactor(Base):
    __tablename__ = "user_mfa_factors"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    factor_type: Mapped[str] = mapped_column(String, nullable=False, server_default="totp")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    secret_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    last_used_step: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    enabled_at: Mapped[str | None] = mapped_column(String)
    __table_args__ = (
        CheckConstraint("factor_type IN ('totp')", name="ck_user_mfa_factors_type"),
        CheckConstraint("status IN ('pending','enabled')", name="ck_user_mfa_factors_status"),
        UniqueConstraint("user_id", "factor_type", name="uq_user_mfa_factors_user_type"),
        Index("idx_user_mfa_factors_user_status", "user_id", "status"),
    )


class MfaRecoveryCode(Base):
    __tablename__ = "mfa_recovery_codes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    used_at: Mapped[str | None] = mapped_column(String)
    __table_args__ = (
        Index("idx_mfa_recovery_codes_user_unused", "user_id", "used_at"),
    )


class MfaLoginChallenge(Base):
    __tablename__ = "mfa_login_challenges"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    expires_at: Mapped[str] = mapped_column(String, nullable=False)
    attempts_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    consumed_at: Mapped[str | None] = mapped_column(String)
    __table_args__ = (
        Index("idx_mfa_login_challenges_user_expires", "user_id", "expires_at"),
    )


class BillingAccount(Base):
    __tablename__ = "billing_accounts"
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String, unique=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String)
    plan: Mapped[str] = mapped_column(String, nullable=False, server_default="free")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="none")
    billing_interval: Mapped[str | None] = mapped_column(String)
    current_period_start: Mapped[str | None] = mapped_column(String)
    current_period_end: Mapped[str | None] = mapped_column(String)
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint("plan IN ('free','pro')", name="ck_billing_accounts_plan"),
        CheckConstraint(
            "status IN ('none','incomplete','incomplete_expired','trialing','active',"
            "'past_due','canceled','unpaid','paused')",
            name="ck_billing_accounts_status",
        ),
        CheckConstraint(
            "billing_interval IS NULL OR billing_interval IN ('month','year')",
            name="ck_billing_accounts_interval",
        ),
    )


class BillingUsageEvent(Base):
    __tablename__ = "billing_usage_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String, nullable=False)
    feature: Mapped[str] = mapped_column(String, nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "user_id", "metric", "request_id", name="uq_billing_usage_request"
        ),
        Index("idx_billing_usage_period", "user_id", "metric", "occurred_at"),
    )


class StripeWebhookEvent(Base):
    __tablename__ = "stripe_webhook_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    processed_at: Mapped[str] = mapped_column(String, nullable=False)


def _default_trade_position_status(context) -> str:
    values = context.get_current_parameters()
    return (
        "closed"
        if any(values.get(field) is not None for field in ("close_price", "close_time", "pnl"))
        else "open"
    )


class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    series_id: Mapped[str | None] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    position_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=_default_trade_position_status,
        server_default="open",
    )
    open_price: Mapped[float | None] = mapped_column(Float)
    close_price: Mapped[float | None] = mapped_column(Float)
    quantity: Mapped[float | None] = mapped_column(Float)
    open_time: Mapped[str | None] = mapped_column(String)
    close_time: Mapped[str | None] = mapped_column(String)
    fees: Mapped[float] = mapped_column(Float, server_default="0")
    pnl: Mapped[float | None] = mapped_column(Float)
    tags: Mapped[str] = mapped_column(Text, server_default="[]")
    notes: Mapped[str] = mapped_column(Text, server_default="")
    ai_review: Mapped[str | None] = mapped_column(Text)
    exchange: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, server_default="manual")
    strategy_id: Mapped[str | None] = mapped_column(String)
    plan_id: Mapped[str | None] = mapped_column(String)
    target_price: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    setup_type: Mapped[str | None] = mapped_column(String)
    emotional_state: Mapped[str | None] = mapped_column(String)
    mistakes: Mapped[str] = mapped_column(Text, server_default="[]")
    confidence: Mapped[int | None] = mapped_column(Integer)
    execution_quality: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint("direction IN ('long','short')", name="ck_trades_direction"),
        CheckConstraint(
            "position_status IN ('open','closed')",
            name="ck_trades_position_status",
        ),
        CheckConstraint(
            "source IN ('manual','screenshot','file_import','recognition')",
            name="ck_trades_source",
        ),
        Index("idx_trades_user_id", "user_id"),
        Index("idx_trades_user_position_status", "user_id", "position_status"),
        Index("idx_trades_symbol", "symbol"),
        Index("idx_trades_series_id", "series_id"),
        Index("idx_trades_open_time", "open_time"),
    )


class TradePlan(Base):
    __tablename__ = "trade_plans"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    series_id: Mapped[str | None] = mapped_column(String)
    market: Mapped[str] = mapped_column(String, nullable=False, server_default="stock")
    direction: Mapped[str] = mapped_column(String, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    target_price: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    account_size: Mapped[float] = mapped_column(Float, nullable=False)
    risk_percent: Mapped[float] = mapped_column(Float, nullable=False)
    thesis: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    strategy_id: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint("direction IN ('long','short')", name="ck_trade_plans_direction"),
        CheckConstraint("status IN ('active','converted')", name="ck_trade_plans_status"),
        Index("idx_trade_plans_user_status", "user_id", "status"),
        Index("idx_trade_plans_series_id", "series_id"),
    )


class TradingRule(Base):
    __tablename__ = "trading_rules"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    rule_type: Mapped[str] = mapped_column(String, nullable=False)
    threshold: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[str] = mapped_column(String, nullable=False, server_default="important")
    active: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint("weight IN ('critical','important','nice_to_have')", name="ck_trading_rules_weight"),
        Index("idx_trading_rules_user_active", "user_id", "active"),
    )


class TradeRuleResult(Base):
    __tablename__ = "trade_rule_results"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    trade_id: Mapped[str] = mapped_column(
        String, ForeignKey("trades.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("trading_rules.id", ondelete="SET NULL")
    )
    rule_name: Mapped[str] = mapped_column(String, nullable=False)
    rule_type: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint("status IN ('passed','failed','not_applicable')", name="ck_trade_rule_results_status"),
        Index("idx_trade_rule_results_trade", "trade_id"),
    )


class UploadedAsset(Base):
    __tablename__ = "uploaded_assets"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    original_name: Mapped[str | None] = mapped_column(String)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (Index("idx_uploaded_assets_user_id", "user_id"),)


class ImageAnnotation(Base):
    __tablename__ = "image_annotations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    asset_id: Mapped[str] = mapped_column(
        String, ForeignKey("uploaded_assets.id", ondelete="CASCADE"), nullable=False
    )
    x_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    y_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "x_ratio >= 0 AND x_ratio <= 1",
            name="ck_image_annotations_x_ratio",
        ),
        CheckConstraint(
            "y_ratio >= 0 AND y_ratio <= 1",
            name="ck_image_annotations_y_ratio",
        ),
        UniqueConstraint(
            "asset_id",
            "sort_order",
            name="uq_image_annotations_asset_order",
        ),
        Index("idx_image_annotations_asset_id", "asset_id"),
    )


class TradeImage(Base):
    __tablename__ = "trade_images"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    trade_id: Mapped[str] = mapped_column(
        String, ForeignKey("trades.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[str] = mapped_column(
        String, ForeignKey("uploaded_assets.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String, server_default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        UniqueConstraint("trade_id", "asset_id", name="uq_trade_images_trade_asset"),
        Index("idx_trade_images_trade_id", "trade_id"),
        Index("idx_trade_images_asset_id", "asset_id"),
    )


class DailyReview(Base):
    __tablename__ = "daily_reviews"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    review_date: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    tags: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        UniqueConstraint("user_id", "review_date", name="uq_daily_reviews_user_date"),
        Index("idx_daily_reviews_user_date", "user_id", "review_date"),
    )


class BacktestStrategy(Base):
    __tablename__ = "backtest_strategies"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    config: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (Index("idx_backtest_strategies_user_id", "user_id"),)


class Strategy(Base):
    __tablename__ = "strategies"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    tags: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (Index("idx_strategies_user_updated", "user_id", column("updated_at").desc()),)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    strategy_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("backtest_strategies.id", ondelete="SET NULL")
    )
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String, nullable=False)
    strategy_config: Mapped[str] = mapped_column(Text, nullable=False)
    run_kind: Mapped[str] = mapped_column(String, nullable=False, server_default="standard")
    analysis_config: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False)
    requested_date_from: Mapped[str | None] = mapped_column(String)
    requested_date_to: Mapped[str | None] = mapped_column(String)
    actual_date_from: Mapped[str | None] = mapped_column(String)
    actual_date_to: Mapped[str | None] = mapped_column(String)
    result: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[str | None] = mapped_column(String)
    completed_at: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        Index("idx_backtest_runs_user_created", "user_id", column("created_at").desc()),
        Index("idx_backtest_runs_strategy_id", "strategy_id"),
        Index("idx_backtest_runs_status", "status"),
    )


class MarketCandle(Base):
    __tablename__ = "market_candles"
    provider_id: Mapped[str] = mapped_column(String, primary_key=True)
    series_id: Mapped[str] = mapped_column(String, primary_key=True)
    timeframe: Mapped[str] = mapped_column(String, primary_key=True)
    open_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
    )
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float)
    is_closed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        Index(
            "idx_market_candles_lookup",
            "provider_id",
            "series_id",
            "timeframe",
            "open_time",
        ),
    )


class MarketCandleCoverage(Base):
    __tablename__ = "market_candle_coverage"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider_id: Mapped[str] = mapped_column(String, nullable=False)
    series_id: Mapped[str] = mapped_column(String, nullable=False)
    instrument_id: Mapped[str] = mapped_column(String, nullable=False)
    listing_id: Mapped[str | None] = mapped_column(String)
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    requested_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_symbol: Mapped[str] = mapped_column(String, nullable=False)
    provider_exchange: Mapped[str | None] = mapped_column(String)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quality_status: Mapped[str] = mapped_column(String, nullable=False)
    quality_warnings: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "series_id",
            "timeframe",
            "purpose",
            "requested_start",
            "requested_end",
            name="uq_market_candle_coverage_request",
        ),
        Index(
            "idx_market_candle_coverage_lookup",
            "provider_id",
            "series_id",
            "timeframe",
            "purpose",
            "requested_start",
            "requested_end",
        ),
    )


class MarketDashboardSnapshot(Base):
    __tablename__ = "market_dashboard_snapshots"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class Portfolio(Base):
    __tablename__ = "portfolios"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)  # no FK in legacy schema
    name: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (Index("idx_portfolios_user_created", "user_id", column("created_at").desc()),)


class PortfolioEntry(Base):
    __tablename__ = "portfolio_entries"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    portfolio_id: Mapped[str] = mapped_column(
        String, ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str | None] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        Index("idx_portfolio_entries_portfolio_updated", "portfolio_id", column("updated_at").desc()),
        Index("idx_portfolio_entries_portfolio_category", "portfolio_id", "category"),
        Index("idx_portfolio_entries_portfolio_platform", "portfolio_id", "platform"),
    )


class PortfolioCategory(Base):
    __tablename__ = "portfolio_categories"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String)  # NULL = preset
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, server_default="100")
    __table_args__ = (
        CheckConstraint("kind IN ('asset','liability')", name="ck_portfolio_categories_kind"),
        UniqueConstraint("user_id", "name", name="uq_portfolio_categories_user_name"),
    )


class JournalSettings(Base):
    __tablename__ = "journal_settings"
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    starting_capital: Mapped[float | None] = mapped_column(Float)
    currency_code: Mapped[str | None] = mapped_column(String(12), nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    pinned_at: Mapped[str | None] = mapped_column(String, nullable=True)
    pinned_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    pending_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pending_at: Mapped[str | None] = mapped_column(String, nullable=True)
    __table_args__ = (Index("idx_chat_conversations_user_updated", "user_id", column("updated_at").desc()),)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    work_log: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    artifacts: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_chat_messages_role"),
        Index("idx_chat_messages_conversation", "conversation_id", "created_at"),
    )


class ChatMessageAttachment(Base):
    __tablename__ = "chat_message_attachments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    message_id: Mapped[str] = mapped_column(
        String, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[str] = mapped_column(
        String, ForeignKey("uploaded_assets.id"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "message_id", "asset_id", name="uq_chat_message_attachments_message_asset",
        ),
        Index("idx_chat_message_attachments_message", "message_id", "sort_order"),
        Index("idx_chat_message_attachments_asset", "asset_id"),
    )


class AssistantMemory(Base):
    __tablename__ = "assistant_memories"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        Index("idx_assistant_memories_user_updated", "user_id", column("updated_at").desc()),
    )


class StrategyEmbedding(Base):
    __tablename__ = "strategy_embeddings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    strategy_id: Mapped[str] = mapped_column(
        String, ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        Index("idx_strategy_embeddings_user", "user_id"),
        Index("idx_strategy_embeddings_strategy", "strategy_id"),
        Index(
            "idx_strategy_embeddings_hnsw", "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        Index("idx_knowledge_chunks_source", "source"),
        Index(
            "idx_knowledge_chunks_hnsw", "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class FeedItem(Base):
    __tablename__ = "feed_items"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    source_key: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    published_at: Mapped[str | None] = mapped_column(String)
    fetched_at: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, server_default="general")
    symbols: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    lang: Mapped[str] = mapped_column(String, nullable=False, server_default="en")
    __table_args__ = (
        Index("idx_feed_items_published", column("published_at").desc()),
        Index("idx_feed_items_category", "category"),
        Index("idx_feed_items_source", "source_key"),
    )


class FeedBriefing(Base):
    __tablename__ = "feed_briefings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    generated_at: Mapped[str] = mapped_column(String, nullable=False)
    lang: Mapped[str] = mapped_column(String, nullable=False)
    window: Mapped[str] = mapped_column(String, nullable=False, server_default="6h")
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    __table_args__ = (Index("idx_feed_briefings_lang_generated", "lang", column("generated_at").desc()),)


class FeedBookmark(Base):
    __tablename__ = "feed_bookmarks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    feed_item_id: Mapped[str] = mapped_column(
        String, ForeignKey("feed_items.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        UniqueConstraint("user_id", "feed_item_id", name="uq_feed_bookmarks_user_item"),
        Index("idx_feed_bookmarks_user", "user_id"),
    )


class NotificationEvent(Base):
    __tablename__ = "notification_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    subject_type: Mapped[str | None] = mapped_column(String)
    subject_id: Mapped[str | None] = mapped_column(String)
    occurred_at: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[str | None] = mapped_column(String)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        Index("idx_notification_events_type", "event_type"),
        Index("idx_notification_events_occurred", "occurred_at"),
        Index("idx_notification_events_subject", "subject_type", "subject_id"),
    )


class NotificationChannel(Base):
    __tablename__ = "notification_channels"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel_type: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    address: Mapped[str | None] = mapped_column(String)
    channel_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    locale: Mapped[str] = mapped_column(String, nullable=False, server_default="zh")
    verification_token_hash: Mapped[str | None] = mapped_column(String)
    verification_expires_at: Mapped[str | None] = mapped_column(String)
    last_error_code: Mapped[str | None] = mapped_column(String)
    last_error_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','active','disabled')",
            name="ck_notification_channels_status",
        ),
        CheckConstraint("locale IN ('zh','en')", name="ck_notification_channels_locale"),
        UniqueConstraint("user_id", "channel_type", name="uq_notification_channels_user_type"),
        Index("idx_notification_channels_user", "user_id"),
        Index(
            "uq_notification_channels_active_address",
            "channel_type", "address",
            unique=True,
            postgresql_where=(column("address").is_not(None) & (column("status") == "active")),
        ),
    )


class NotificationSubscription(Base):
    __tablename__ = "notification_subscriptions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[str] = mapped_column(
        String, ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    subject_type: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    subject_id: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    locale: Mapped[str] = mapped_column(String, nullable=False, server_default="zh")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint("locale IN ('zh','en')", name="ck_notification_subscriptions_locale"),
        UniqueConstraint(
            "user_id", "channel_id", "event_type", "subject_type", "subject_id",
            name="uq_notification_subscriptions_target",
        ),
        Index(
            "idx_notification_subscriptions_match",
            "event_type", "subject_type", "subject_id", "enabled",
        ),
        Index("idx_notification_subscriptions_user", "user_id"),
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        String, ForeignKey("notification_events.id", ondelete="CASCADE"), nullable=False
    )
    subscription_id: Mapped[str] = mapped_column(
        String, ForeignKey("notification_subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[str] = mapped_column(
        String, ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    next_attempt_at: Mapped[str | None] = mapped_column(String)
    claimed_at: Mapped[str | None] = mapped_column(String)
    sent_at: Mapped[str | None] = mapped_column(String)
    read_at: Mapped[str | None] = mapped_column(String)
    provider_message_id: Mapped[str | None] = mapped_column(String)
    last_error_code: Mapped[str | None] = mapped_column(String)
    last_error_message: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processing','sent','retrying','failed','expired','unknown')",
            name="ck_notification_deliveries_status",
        ),
        UniqueConstraint(
            "event_id", "subscription_id", "channel_id",
            name="uq_notification_deliveries_target",
        ),
        Index("idx_notification_deliveries_queue", "status", "next_attempt_at"),
        Index("idx_notification_deliveries_created", "created_at"),
        Index(
            "idx_notification_deliveries_channel_read",
            "channel_id", "read_at", "created_at",
        ),
    )


class AutomationTask(Base):
    __tablename__ = "automation_tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    task_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="active")
    schedule_kind: Mapped[str] = mapped_column(String, nullable=False)
    schedule_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    timezone: Mapped[str] = mapped_column(String, nullable=False, server_default="UTC")
    scope: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notification_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    next_run_at: Mapped[str] = mapped_column(String, nullable=False)
    last_run_at: Mapped[str | None] = mapped_column(String)
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "task_type IN ("
            "'risk_guardian','news_impact','market_watch','condition_monitor',"
            "'session_report','plan_guardian'"
            ")",
            name="ck_automation_tasks_type",
        ),
        CheckConstraint(
            "status IN ('active','paused','disabled')",
            name="ck_automation_tasks_status",
        ),
        CheckConstraint(
            "schedule_kind IN ('interval','daily')",
            name="ck_automation_tasks_schedule_kind",
        ),
        Index("idx_automation_tasks_due", "status", "next_run_at"),
        Index("idx_automation_tasks_user", "user_id", "status"),
    )


class AutomationRun(Base):
    __tablename__ = "automation_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("automation_tasks.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    trigger_kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="queued")
    scheduled_for: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[str | None] = mapped_column(String)
    finished_at: Mapped[str | None] = mapped_column(String)
    lease_expires_at: Mapped[str | None] = mapped_column(String)
    input_as_of: Mapped[str | None] = mapped_column(String)
    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "trigger_kind IN ('scheduled','manual')",
            name="ck_automation_runs_trigger",
        ),
        CheckConstraint(
            "status IN ('queued','running','succeeded','partial','failed','skipped')",
            name="ck_automation_runs_status",
        ),
        UniqueConstraint(
            "task_id", "scheduled_for", name="uq_automation_runs_task_schedule"
        ),
        Index("idx_automation_runs_task_created", "task_id", column("created_at").desc()),
        Index("idx_automation_runs_lease", "status", "lease_expires_at"),
    )


class AgentFinding(Base):
    __tablename__ = "agent_findings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("automation_tasks.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        String, ForeignKey("automation_runs.id", ondelete="CASCADE"), nullable=False
    )
    finding_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="open")
    fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    subject_type: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    subject_id: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    first_seen_at: Mapped[str] = mapped_column(String, nullable=False)
    last_seen_at: Mapped[str] = mapped_column(String, nullable=False)
    resolved_at: Mapped[str | None] = mapped_column(String)
    expires_at: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "finding_type IN ('risk','news','data_quality','market','plan')",
            name="ck_agent_findings_type",
        ),
        CheckConstraint(
            "severity IN ('info','warning','critical')",
            name="ck_agent_findings_severity",
        ),
        CheckConstraint(
            "status IN ('open','acknowledged','resolved','suppressed')",
            name="ck_agent_findings_status",
        ),
        Index(
            "idx_agent_findings_user_status",
            "user_id", "status", "severity", column("last_seen_at").desc(),
        ),
        Index("idx_agent_findings_task", "task_id", "status"),
        Index("idx_agent_findings_fingerprint", "user_id", "fingerprint"),
    )


class TradeImportBatch(Base):
    __tablename__ = "trade_import_batches"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[str] = mapped_column(
        String, ForeignKey("uploaded_assets.id", ondelete="CASCADE"), nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String, nullable=False)
    source_name: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="preparing")
    mapping: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    committed_at: Mapped[str | None] = mapped_column(String)
    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('csv','json','xlsx','image')",
            name="ck_trade_import_batches_source",
        ),
        CheckConstraint(
            "status IN ('preparing','needs_review','ready','committing','committed','failed','cancelled')",
            name="ck_trade_import_batches_status",
        ),
        Index("idx_trade_import_batches_user", "user_id", column("created_at").desc()),
    )


class TradeImportRow(Base):
    __tablename__ = "trade_import_rows"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        String, ForeignKey("trade_import_batches.id", ondelete="CASCADE"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    record_kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    normalized_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    fingerprint: Mapped[str | None] = mapped_column(String)
    trade_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("trades.id", ondelete="SET NULL")
    )
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (
        CheckConstraint(
            "record_kind IN ('fill','trade')",
            name="ck_trade_import_rows_kind",
        ),
        CheckConstraint(
            "status IN ('valid','warning','invalid','duplicate','committed')",
            name="ck_trade_import_rows_status",
        ),
        UniqueConstraint("batch_id", "row_number", name="uq_trade_import_rows_batch_row"),
        Index("idx_trade_import_rows_batch", "batch_id", "status"),
        Index("idx_trade_import_rows_fingerprint", "fingerprint"),
    )
