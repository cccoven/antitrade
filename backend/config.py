import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=False)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://antitrade:antitrade@localhost:5433/antitrade",
)

# LLM Configuration (env vars override defaults)
# LLM_PROVIDER: "demo" | "openai" | "anthropic"
# The AI assistant (OpenAI Agents SDK) reaches every provider through the
# OpenAI-compatible Chat Completions API: for "anthropic", point LLM_BASE_URL at
# Anthropic's compatible endpoint (https://api.anthropic.com/v1). The chart-analysis
# path (services/analyzer.py) still uses the native anthropic SDK.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "opus")
LLM_VISION_ENABLED = os.environ.get("LLM_VISION_ENABLED", "0") == "1"
LLM_VISION_DETAIL = os.environ.get("LLM_VISION_DETAIL", "high")

EMBEDDINGS_PROVIDER = os.environ.get(
    "EMBEDDINGS_PROVIDER", "demo" if LLM_PROVIDER == "demo" else "openai",
)
EMBEDDINGS_MODEL = os.environ.get("EMBEDDINGS_MODEL", "text-embedding-3-small")
# Embeddings endpoint is decoupled from chat: set these to point embeddings at a
# different OpenAI-compatible endpoint (e.g. chat on DeepSeek, embeddings on OpenAI/GLM).
# When unset, they fall back to LLM_BASE_URL / LLM_API_KEY (backward compatible).
EMBEDDINGS_BASE_URL = os.environ.get("EMBEDDINGS_BASE_URL")
EMBEDDINGS_API_KEY = os.environ.get("EMBEDDINGS_API_KEY")

# Free-tier market research providers used by the AI assistant.
TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")

# Optional live web search used by the AI assistant. When unset, the frontend
# exposes the feature as unavailable and the agent never receives the tool.
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

# JWT Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7
MFA_ENCRYPTION_KEY = os.environ.get("MFA_ENCRYPTION_KEY", "")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()

# Radar feed configuration
RSSHUB_BASE_URL = os.environ.get("RSSHUB_BASE_URL", "http://localhost:1200")
FEED_INGEST_MINUTES = int(os.environ.get("FEED_INGEST_MINUTES", "3"))
FEED_BRIEFING_MINUTES = int(os.environ.get("FEED_BRIEFING_MINUTES", "60"))
FEED_BRIEFING_WINDOW_HOURS = int(os.environ.get("FEED_BRIEFING_WINDOW_HOURS", "6"))
MARKET_OVERVIEW_REFRESH_SECONDS = max(
    15,
    int(os.environ.get("MARKET_OVERVIEW_REFRESH_SECONDS", "30")),
)
DAILY_MARKET_BRIEFING_REFRESH_MINUTES = max(
    5,
    int(os.environ.get("DAILY_MARKET_BRIEFING_REFRESH_MINUTES", "15")),
)
SCHEDULER_ENABLED = os.environ.get("SCHEDULER_ENABLED", "1") == "1"
AUTOMATION_TASKS_ENABLED = os.environ.get("AUTOMATION_TASKS_ENABLED", "1") == "1"
AUTOMATION_POLL_SECONDS = max(15, int(os.environ.get("AUTOMATION_POLL_SECONDS", "30")))

# Notification channels
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
APP_PUBLIC_URL = os.environ.get("APP_PUBLIC_URL", "").rstrip("/")
TELEGRAM_WEBHOOK_BASE_URL = os.environ.get(
    "TELEGRAM_WEBHOOK_BASE_URL", APP_PUBLIC_URL
).rstrip("/")

# Stripe Billing. Price IDs are created in Stripe and selected server-side;
# clients only choose a billing interval.
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRO_MONTHLY_PRICE_ID = os.environ.get("STRIPE_PRO_MONTHLY_PRICE_ID", "")
STRIPE_PRO_YEARLY_PRICE_ID = os.environ.get("STRIPE_PRO_YEARLY_PRICE_ID", "")
BILLING_CURRENCY = os.environ.get("BILLING_CURRENCY", "USD").upper()
BILLING_PRO_MONTHLY_AMOUNT = int(os.environ.get("BILLING_PRO_MONTHLY_AMOUNT", "900"))
BILLING_PRO_YEARLY_AMOUNT = int(os.environ.get("BILLING_PRO_YEARLY_AMOUNT", "9000"))
BILLING_FREE_AI_UNITS = int(os.environ.get("BILLING_FREE_AI_UNITS", "20"))
BILLING_PRO_AI_UNITS = int(os.environ.get("BILLING_PRO_AI_UNITS", "300"))
