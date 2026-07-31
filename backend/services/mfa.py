"""TOTP MFA enrollment, login challenges, and recovery-code management."""

import base64
import hashlib
import hmac
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from config import MFA_ENCRYPTION_KEY
from models import MfaLoginChallenge, MfaRecoveryCode, User, UserMfaFactor


TOTP_INTERVAL_SECONDS = 30
TOTP_VALID_WINDOW = 1
LOGIN_CHALLENGE_SECONDS = 300
LOGIN_CHALLENGE_ATTEMPTS = 5
RECOVERY_CODE_COUNT = 10


class MfaError(ValueError):
    """Expected MFA failure whose message is an i18n key."""


class MfaConfigurationError(RuntimeError):
    """Raised when server-side MFA encryption is unavailable."""


class MfaService:
    def __init__(
        self,
        session: Session,
        password_verifier: Callable[[str, str], bool],
        *,
        now_factory: Callable[[], datetime] | None = None,
    ):
        self.session = session
        self.password_verifier = password_verifier
        self.now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def get_status(self, user_id: str) -> dict:
        factor = self.session.execute(
            select(UserMfaFactor).where(
                UserMfaFactor.user_id == user_id,
                UserMfaFactor.factor_type == "totp",
                UserMfaFactor.status == "enabled",
            )
        ).scalar_one_or_none()
        remaining = 0
        if factor is not None:
            remaining = int(self.session.scalar(
                select(func.count())
                .select_from(MfaRecoveryCode)
                .where(
                    MfaRecoveryCode.user_id == user_id,
                    MfaRecoveryCode.used_at.is_(None),
                )
            ) or 0)
        return {
            "enabled": factor is not None,
            "enabled_at": factor.enabled_at if factor is not None else None,
            "recovery_codes_remaining": remaining,
        }

    def has_enabled_factor(self, user_id: str) -> bool:
        return self.session.scalar(
            select(UserMfaFactor.id).where(
                UserMfaFactor.user_id == user_id,
                UserMfaFactor.factor_type == "totp",
                UserMfaFactor.status == "enabled",
            )
        ) is not None

    def start_enrollment(self, user_id: str, current_password: str) -> dict:
        user = self._verify_account_password(user_id, current_password)
        existing = self.session.execute(
            select(UserMfaFactor)
            .where(
                UserMfaFactor.user_id == user_id,
                UserMfaFactor.factor_type == "totp",
            )
            .with_for_update()
        ).scalar_one_or_none()
        if existing is not None and existing.status == "enabled":
            raise MfaError("mfa.error.already_enabled")

        secret = pyotp.random_base32(length=32)
        ciphertext = self._encrypt_secret(secret)
        now = self._now()
        if existing is None:
            self.session.add(UserMfaFactor(
                id=str(uuid4()),
                user_id=user_id,
                factor_type="totp",
                status="pending",
                secret_ciphertext=ciphertext,
                last_used_step=None,
                created_at=now.isoformat(),
                enabled_at=None,
            ))
        else:
            existing.secret_ciphertext = ciphertext
            existing.last_used_step = None
            existing.created_at = now.isoformat()
            existing.enabled_at = None
        self.session.commit()

        uri = pyotp.TOTP(
            secret,
            digits=6,
            interval=TOTP_INTERVAL_SECONDS,
        ).provisioning_uri(name=user.email, issuer_name="AntiTrade")
        return {"otpauth_uri": uri, "manual_key": secret}

    def confirm_enrollment(self, user_id: str, code: str) -> dict:
        user = self.session.execute(
            select(User).where(User.id == user_id).with_for_update()
        ).scalar_one_or_none()
        factor = self.session.execute(
            select(UserMfaFactor)
            .where(
                UserMfaFactor.user_id == user_id,
                UserMfaFactor.factor_type == "totp",
                UserMfaFactor.status == "pending",
            )
            .with_for_update()
        ).scalar_one_or_none()
        if user is None or factor is None:
            raise MfaError("mfa.error.setup_not_started")

        step = self._matching_totp_step(
            self._decrypt_secret(factor.secret_ciphertext),
            code,
            factor.last_used_step,
        )
        if step is None:
            raise MfaError("mfa.error.invalid_code")

        now = self._now().isoformat()
        factor.status = "enabled"
        factor.enabled_at = now
        factor.last_used_step = step
        recovery_codes = self._replace_recovery_codes(user_id, now)
        user.auth_version += 1
        self.session.commit()
        return {"user_id": user_id, "recovery_codes": recovery_codes}

    def create_login_challenge(self, user_id: str) -> dict:
        if not self.has_enabled_factor(user_id):
            raise MfaError("mfa.error.not_enabled")

        now = self._now()
        self.session.execute(
            update(MfaLoginChallenge)
            .where(
                MfaLoginChallenge.user_id == user_id,
                MfaLoginChallenge.consumed_at.is_(None),
            )
            .values(consumed_at=now.isoformat())
        )
        token = secrets.token_urlsafe(32)
        self.session.add(MfaLoginChallenge(
            id=str(uuid4()),
            user_id=user_id,
            token_hash=self._challenge_hash(token),
            expires_at=(now + timedelta(seconds=LOGIN_CHALLENGE_SECONDS)).isoformat(),
            attempts_remaining=LOGIN_CHALLENGE_ATTEMPTS,
            created_at=now.isoformat(),
            consumed_at=None,
        ))
        self.session.commit()
        return {"token": token, "expires_in": LOGIN_CHALLENGE_SECONDS}

    def complete_login_challenge(self, challenge_token: str, code: str) -> str:
        challenge = self.session.execute(
            select(MfaLoginChallenge)
            .where(MfaLoginChallenge.token_hash == self._challenge_hash(challenge_token))
            .with_for_update()
        ).scalar_one_or_none()
        now = self._now()
        if challenge is None or challenge.consumed_at is not None:
            raise MfaError("mfa.error.invalid_challenge")
        if self._parse_time(challenge.expires_at) <= now:
            challenge.consumed_at = now.isoformat()
            self.session.commit()
            raise MfaError("mfa.error.invalid_challenge")
        if challenge.attempts_remaining <= 0:
            challenge.consumed_at = now.isoformat()
            self.session.commit()
            raise MfaError("mfa.error.invalid_challenge")

        if not self._verify_factor_code(challenge.user_id, code):
            challenge.attempts_remaining -= 1
            if challenge.attempts_remaining <= 0:
                challenge.consumed_at = now.isoformat()
            self.session.commit()
            raise MfaError("mfa.error.invalid_code")

        challenge.consumed_at = now.isoformat()
        self.session.commit()
        return challenge.user_id

    def disable(self, user_id: str, current_password: str, code: str) -> str:
        user = self._verify_account_password(user_id, current_password)
        if not self._verify_factor_code(user_id, code):
            raise MfaError("mfa.error.invalid_code")
        self.session.execute(
            delete(UserMfaFactor).where(UserMfaFactor.user_id == user_id)
        )
        self.session.execute(
            delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id)
        )
        self.session.execute(
            delete(MfaLoginChallenge).where(MfaLoginChallenge.user_id == user_id)
        )
        user.auth_version += 1
        self.session.commit()
        return user_id

    def regenerate_recovery_codes(
        self,
        user_id: str,
        current_password: str,
        code: str,
    ) -> list[str]:
        self._verify_account_password(user_id, current_password)
        if not self._verify_factor_code(user_id, code):
            raise MfaError("mfa.error.invalid_code")
        recovery_codes = self._replace_recovery_codes(
            user_id,
            self._now().isoformat(),
        )
        self.session.commit()
        return recovery_codes

    def _verify_account_password(self, user_id: str, current_password: str) -> User:
        user = self.session.execute(
            select(User).where(User.id == user_id).with_for_update()
        ).scalar_one_or_none()
        if user is None:
            raise MfaError("auth.error.user_not_found")
        if not self.password_verifier(current_password, user.password):
            raise MfaError("auth.error.current_password_incorrect")
        return user

    def _verify_factor_code(self, user_id: str, code: str) -> bool:
        factor = self.session.execute(
            select(UserMfaFactor)
            .where(
                UserMfaFactor.user_id == user_id,
                UserMfaFactor.factor_type == "totp",
                UserMfaFactor.status == "enabled",
            )
            .with_for_update()
        ).scalar_one_or_none()
        if factor is None:
            return False

        normalized = code.strip().replace(" ", "").replace("-", "").upper()
        if len(normalized) == 6 and normalized.isdigit():
            step = self._matching_totp_step(
                self._decrypt_secret(factor.secret_ciphertext),
                normalized,
                factor.last_used_step,
            )
            if step is None:
                return False
            factor.last_used_step = step
            return True

        code_hash = self._recovery_hash(user_id, normalized)
        recovery_code = self.session.execute(
            select(MfaRecoveryCode)
            .where(
                MfaRecoveryCode.user_id == user_id,
                MfaRecoveryCode.code_hash == code_hash,
                MfaRecoveryCode.used_at.is_(None),
            )
            .with_for_update()
        ).scalar_one_or_none()
        if recovery_code is None:
            return False
        recovery_code.used_at = self._now().isoformat()
        return True

    def _matching_totp_step(
        self,
        secret: str,
        code: str,
        last_used_step: int | None,
    ) -> int | None:
        normalized = code.strip()
        if len(normalized) != 6 or not normalized.isdigit():
            return None
        current_step = int(self._now().timestamp()) // TOTP_INTERVAL_SECONDS
        totp = pyotp.TOTP(secret, digits=6, interval=TOTP_INTERVAL_SECONDS)
        matching_steps = [
            step
            for step in range(
                current_step - TOTP_VALID_WINDOW,
                current_step + TOTP_VALID_WINDOW + 1,
            )
            if hmac.compare_digest(
                totp.at(step * TOTP_INTERVAL_SECONDS),
                normalized,
            )
        ]
        if not matching_steps:
            return None
        matched = max(matching_steps)
        if last_used_step is not None and matched <= last_used_step:
            return None
        return matched

    def _replace_recovery_codes(self, user_id: str, created_at: str) -> list[str]:
        self.session.execute(
            delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id)
        )
        codes: list[str] = []
        for _ in range(RECOVERY_CODE_COUNT):
            normalized = secrets.token_hex(8).upper()
            display_code = "-".join(
                normalized[index:index + 4]
                for index in range(0, len(normalized), 4)
            )
            codes.append(display_code)
            self.session.add(MfaRecoveryCode(
                id=str(uuid4()),
                user_id=user_id,
                code_hash=self._recovery_hash(user_id, normalized),
                created_at=created_at,
                used_at=None,
            ))
        return codes

    def _encrypt_secret(self, secret: str) -> str:
        return self._cipher().encrypt(secret.encode("ascii")).decode("ascii")

    def _decrypt_secret(self, ciphertext: str) -> str:
        try:
            return self._cipher().decrypt(ciphertext.encode("ascii")).decode("ascii")
        except InvalidToken as exc:
            raise MfaConfigurationError("mfa_secret_unavailable") from exc

    def _cipher(self) -> Fernet:
        if not MFA_ENCRYPTION_KEY:
            raise MfaConfigurationError("mfa_encryption_key_missing")
        try:
            return Fernet(MFA_ENCRYPTION_KEY.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise MfaConfigurationError("mfa_encryption_key_invalid") from exc

    def _recovery_hash(self, user_id: str, normalized_code: str) -> str:
        try:
            key = base64.urlsafe_b64decode(MFA_ENCRYPTION_KEY.encode("ascii"))
        except (ValueError, TypeError) as exc:
            raise MfaConfigurationError("mfa_encryption_key_invalid") from exc
        if len(key) != 32:
            raise MfaConfigurationError("mfa_encryption_key_invalid")
        return hmac.new(
            key,
            f"{user_id}:{normalized_code}".encode("ascii"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _challenge_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_time(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _now(self) -> datetime:
        now = self.now_factory()
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)
