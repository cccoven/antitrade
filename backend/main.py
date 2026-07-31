import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import HTTPException
from api_response import error
from i18n import t, get_lang
from services.billing import (
    BillingAccessError,
    BillingConfigurationError,
    BillingConflictError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AntiTrade API starting up")
    from db import SessionLocal
    from scheduler import start_scheduler, shutdown_scheduler
    from services.backtest import BacktestService
    from services.feed_ingest import repair_feed_item_languages
    from services.telegram_channel import configure_telegram_webhook
    try:
        with SessionLocal() as session:
            repaired = repair_feed_item_languages(session)
        if repaired:
            logger.info("Corrected language metadata for %s feed items", repaired)
    except Exception:
        logger.warning("Could not repair legacy feed language metadata", exc_info=True)
    configure_telegram_webhook()
    start_scheduler()
    resumed_backtests = await BacktestService.resume_pending_runs()
    if resumed_backtests:
        logger.info("Resumed %s pending backtest runs", resumed_backtests)
    yield
    shutdown_scheduler()
    logger.info("AntiTrade API shutting down")

app = FastAPI(title="AntiTrade", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(BillingAccessError)
async def handle_billing_access_error(request: Request, exc: BillingAccessError):
    return error(
        message=t(f"billing.error.{exc.reason}", get_lang(request)),
        code=402,
        status_code=402,
        data={"feature": exc.feature, "reason": exc.reason, "usage": exc.usage},
    )


@app.exception_handler(BillingConfigurationError)
async def handle_billing_configuration_error(request: Request, exc: BillingConfigurationError):
    key = "stripe_unavailable" if str(exc) == "stripe_unavailable" else "stripe_not_configured"
    return error(message=t(f"billing.error.{key}", get_lang(request)), code=503, status_code=503)


@app.exception_handler(BillingConflictError)
async def handle_billing_conflict_error(request: Request, exc: BillingConflictError):
    return error(message=t(f"billing.error.{exc}", get_lang(request)), code=409, status_code=409)


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    message = exc.detail if isinstance(exc.detail, str) else t("error.request_failed", get_lang(request))
    return error(message=message, code=exc.status_code, status_code=exc.status_code)


@app.exception_handler(StarletteHTTPException)
async def handle_starlette_http_exception(request: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else t("error.request_failed", get_lang(request))
    return error(message=message, code=exc.status_code, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def handle_validation_exception(request: Request, __: RequestValidationError):
    return error(message=t("error.invalid_params", get_lang(request)), code=400, status_code=400)


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception):
    logger.exception("Unhandled server error", exc_info=exc)
    return error(message=t("error.internal", get_lang(request)), code=500, status_code=500)

from routers import analyze, journal, recognition, chat, auth, backtest, replay, portfolio, uploads, strategies, feed, market, notifications, billing, trading_tools, automations, trade_imports
app.include_router(analyze.router)
app.include_router(journal.router)
app.include_router(recognition.router)
app.include_router(chat.router)
app.include_router(auth.router)
app.include_router(backtest.router)
app.include_router(replay.router)
app.include_router(portfolio.router)
app.include_router(uploads.router)
app.include_router(strategies.router)
app.include_router(feed.router)
app.include_router(market.router)
app.include_router(notifications.router)
app.include_router(billing.router)
app.include_router(trading_tools.router)
app.include_router(automations.router)
app.include_router(trade_imports.router)
