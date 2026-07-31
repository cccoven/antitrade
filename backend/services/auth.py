"""Auth service — user registration, login, JWT token management."""
import re
import logging
import secrets
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import delete, or_, select

from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_DAYS
from models import (
    AgentFinding,
    AssistantMemory,
    AutomationRun,
    AutomationTask,
    BacktestRun,
    BacktestStrategy,
    BillingAccount,
    BillingUsageEvent,
    ChatConversation,
    ChatMessage,
    ChatMessageAttachment,
    DailyReview,
    FeedBookmark,
    JournalSettings,
    NotificationChannel,
    NotificationDelivery,
    NotificationSubscription,
    Portfolio,
    PortfolioCategory,
    PortfolioEntry,
    Strategy,
    StrategyEmbedding,
    Trade,
    TradeImage,
    TradeImportBatch,
    TradeImportRow,
    TradePlan,
    TradeRuleResult,
    TradingRule,
    UploadedAsset,
    User,
    UserOAuthIdentity,
)
from services.google_auth import GoogleAuthError, verify_google_id_token
from services.uploads import delete_user_uploads
from services.mfa import MfaService

logger = logging.getLogger(__name__)
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
ACTIVE_SUBSCRIPTION_STATUSES = {
    "active", "incomplete", "past_due", "paused", "trialing", "unpaid",
}


class AuthService:
    def __init__(self, session: Session):
        self.session = session

    def register(self, email: str, password: str, name: str | None = None) -> dict:
        email = email.strip().lower()
        if not EMAIL_RE.match(email):
            raise ValueError("Invalid email format")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
        existing = self.session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if existing:
            raise ValueError("Email already registered")
        user_id = str(uuid4())
        hashed = _pwd.hash(password)
        display_name = name.strip() if name and name.strip() else email.split("@")[0]
        now = datetime.now(timezone.utc).isoformat()
        user = User(
            id=user_id,
            email=email,
            password=hashed,
            password_set=True,
            name=display_name,
            created_at=now,
        )
        self.session.add(user)
        self.session.commit()
        return self._auth_result(user)

    def login(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        user = self.session.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if not user or not user.password_set or not _pwd.verify(password, user.password):
            raise ValueError("Invalid email or password")
        mfa = self._mfa()
        if mfa.has_enabled_factor(user.id):
            return {
                "mfa_required": True,
                "challenge": mfa.create_login_challenge(user.id),
            }
        return {"mfa_required": False, **self._auth_result(user)}

    def login_with_google(self, credential: str) -> dict:
        claims = verify_google_id_token(credential)
        subject = claims["sub"]
        email = claims["email"].strip().lower()

        identity = self.session.execute(
            select(UserOAuthIdentity).where(
                UserOAuthIdentity.provider == "google",
                UserOAuthIdentity.subject == subject,
            )
        ).scalar_one_or_none()
        user = self.session.get(User, identity.user_id) if identity else None

        if user is None:
            user = self.session.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()
            now = datetime.now(timezone.utc).isoformat()
            if user is None:
                user = User(
                    id=str(uuid4()),
                    email=email,
                    password=_pwd.hash(secrets.token_urlsafe(48)),
                    password_set=False,
                    name=claims.get("name", "").strip() or email.split("@")[0],
                    created_at=now,
                )
                self.session.add(user)
                self.session.flush()
            elif (
                not email.endswith("@gmail.com")
                and not claims.get("hosted_domain")
            ):
                raise GoogleAuthError(
                    "This email is already registered. Sign in with password."
                )
            self.session.add(
                UserOAuthIdentity(
                    id=str(uuid4()),
                    user_id=user.id,
                    provider="google",
                    subject=subject,
                    created_at=now,
                )
            )
            self.session.commit()

        mfa = self._mfa()
        if mfa.has_enabled_factor(user.id):
            return {
                "mfa_required": True,
                "challenge": mfa.create_login_challenge(user.id),
            }
        return {"mfa_required": False, **self._auth_result(user)}

    def get_user(self, user_id: str) -> dict | None:
        user = self.session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        if not user:
            return None
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "has_password": user.password_set,
        }

    def update_profile(self, user_id: str, name: str) -> dict | None:
        name = name.strip()
        if not name:
            raise ValueError("Name cannot be empty")
        user = self.session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        if user:
            user.name = name
            self.session.commit()
        return self.get_user(user_id)

    def change_password(
        self,
        user_id: str,
        current_password: str | None,
        new_password: str,
    ) -> dict:
        user = self.session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()
        if user is None:
            raise ValueError("auth.error.user_not_found")
        if user.password_set and (
            not current_password or not _pwd.verify(current_password, user.password)
        ):
            raise ValueError("auth.error.current_password_incorrect")
        if len(new_password) < 6:
            raise ValueError("auth.error.password_too_short")
        if user.password_set and _pwd.verify(new_password, user.password):
            raise ValueError("auth.error.password_unchanged")
        user.password = _pwd.hash(new_password)
        user.password_set = True
        user.auth_version += 1
        self.session.commit()
        return self._auth_result(user)

    def get_mfa_status(self, user_id: str) -> dict:
        return self._mfa().get_status(user_id)

    def start_mfa_enrollment(self, user_id: str, current_password: str) -> dict:
        return self._mfa().start_enrollment(user_id, current_password)

    def confirm_mfa_enrollment(self, user_id: str, code: str) -> dict:
        result = self._mfa().confirm_enrollment(user_id, code)
        return {
            **self._auth_result_for_user_id(result["user_id"]),
            "recovery_codes": result["recovery_codes"],
        }

    def complete_mfa_login(self, challenge_token: str, code: str) -> dict:
        user_id = self._mfa().complete_login_challenge(challenge_token, code)
        return self._auth_result_for_user_id(user_id)

    def disable_mfa(
        self,
        user_id: str,
        current_password: str,
        code: str,
    ) -> dict:
        verified_user_id = self._mfa().disable(user_id, current_password, code)
        return self._auth_result_for_user_id(verified_user_id)

    def regenerate_mfa_recovery_codes(
        self,
        user_id: str,
        current_password: str,
        code: str,
    ) -> list[str]:
        return self._mfa().regenerate_recovery_codes(
            user_id,
            current_password,
            code,
        )

    def delete_account(self, user_id: str, current_password: str) -> None:
        user = self.session.get(User, user_id)
        if user is None:
            raise ValueError("auth.error.user_not_found")
        if not _pwd.verify(current_password, user.password):
            raise ValueError("auth.error.current_password_incorrect")

        billing_account = self.session.get(BillingAccount, user_id)
        if (
            billing_account is not None
            and billing_account.stripe_subscription_id
            and billing_account.status in ACTIVE_SUBSCRIPTION_STATUSES
        ):
            raise ValueError("auth.error.active_subscription")

        trade_ids = select(Trade.id).where(Trade.user_id == user_id)
        rule_ids = select(TradingRule.id).where(TradingRule.user_id == user_id)
        asset_ids = select(UploadedAsset.id).where(UploadedAsset.user_id == user_id)
        batch_ids = select(TradeImportBatch.id).where(TradeImportBatch.user_id == user_id)
        portfolio_ids = select(Portfolio.id).where(Portfolio.user_id == user_id)
        conversation_ids = select(ChatConversation.id).where(ChatConversation.user_id == user_id)
        message_ids = select(ChatMessage.id).where(
            ChatMessage.conversation_id.in_(conversation_ids)
        )
        subscription_ids = select(NotificationSubscription.id).where(
            NotificationSubscription.user_id == user_id
        )
        channel_ids = select(NotificationChannel.id).where(
            NotificationChannel.user_id == user_id
        )

        try:
            self._delete(
                ChatMessageAttachment,
                or_(
                    ChatMessageAttachment.message_id.in_(message_ids),
                    ChatMessageAttachment.asset_id.in_(asset_ids),
                ),
            )
            self._delete(ChatMessage, ChatMessage.conversation_id.in_(conversation_ids))
            self._delete(ChatConversation, ChatConversation.user_id == user_id)

            self._delete(
                TradeRuleResult,
                or_(
                    TradeRuleResult.trade_id.in_(trade_ids),
                    TradeRuleResult.rule_id.in_(rule_ids),
                ),
            )
            self._delete(
                TradeImage,
                or_(
                    TradeImage.trade_id.in_(trade_ids),
                    TradeImage.asset_id.in_(asset_ids),
                ),
            )
            self._delete(TradeImportRow, TradeImportRow.batch_id.in_(batch_ids))
            self._delete(TradeImportBatch, TradeImportBatch.user_id == user_id)

            self._delete(
                NotificationDelivery,
                or_(
                    NotificationDelivery.subscription_id.in_(subscription_ids),
                    NotificationDelivery.channel_id.in_(channel_ids),
                ),
            )
            self._delete(
                NotificationSubscription,
                NotificationSubscription.user_id == user_id,
            )
            self._delete(NotificationChannel, NotificationChannel.user_id == user_id)

            self._delete(AgentFinding, AgentFinding.user_id == user_id)
            self._delete(AutomationRun, AutomationRun.user_id == user_id)
            self._delete(AutomationTask, AutomationTask.user_id == user_id)

            self._delete(PortfolioEntry, PortfolioEntry.portfolio_id.in_(portfolio_ids))
            self._delete(Portfolio, Portfolio.user_id == user_id)
            self._delete(PortfolioCategory, PortfolioCategory.user_id == user_id)

            self._delete(BacktestRun, BacktestRun.user_id == user_id)
            self._delete(BacktestStrategy, BacktestStrategy.user_id == user_id)
            self._delete(StrategyEmbedding, StrategyEmbedding.user_id == user_id)
            self._delete(Strategy, Strategy.user_id == user_id)

            for model in (
                FeedBookmark,
                AssistantMemory,
                JournalSettings,
                DailyReview,
                TradePlan,
                TradingRule,
                Trade,
                UploadedAsset,
                BillingUsageEvent,
                BillingAccount,
            ):
                self._delete(model, model.user_id == user_id)

            self.session.delete(user)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

        delete_user_uploads(user_id)

    def _delete(self, model, condition) -> None:
        self.session.execute(
            delete(model).where(condition),
            execution_options={"synchronize_session": False},
        )

    def verify_token(self, token: str) -> str | None:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub")
            token_version = payload.get("ver", 0)
            if not isinstance(user_id, str) or not isinstance(token_version, int):
                return None
            user = self.session.get(User, user_id)
            if user is None or user.auth_version != token_version:
                return None
            return user_id
        except JWTError:
            return None

    def _auth_result_for_user_id(self, user_id: str) -> dict:
        user = self.session.get(User, user_id)
        if user is None:
            raise ValueError("auth.error.user_not_found")
        return self._auth_result(user)

    def _auth_result(self, user: User) -> dict:
        return {
            "token": self._create_token(user.id, user.auth_version),
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "has_password": user.password_set,
            },
        }

    def _mfa(self) -> MfaService:
        return MfaService(self.session, _pwd.verify)

    def _create_token(self, user_id: str, auth_version: int) -> str:
        expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
        return jwt.encode(
            {"sub": user_id, "ver": auth_version, "exp": expire},
            JWT_SECRET,
            algorithm=JWT_ALGORITHM,
        )
