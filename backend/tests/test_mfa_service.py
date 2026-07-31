"""Focused tests for TOTP MFA state and one-time semantics."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pyotp
import pytest
from passlib.context import CryptContext
from sqlalchemy import select

from models import MfaLoginChallenge, MfaRecoveryCode, User, UserMfaFactor
from services.mfa import LOGIN_CHALLENGE_ATTEMPTS, MfaError, MfaService


_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
NOW = datetime(2026, 7, 24, 8, 0, 0, tzinfo=timezone.utc)


def _create_user(db, email: str = "mfa@example.com") -> User:
    user = User(
        id=str(uuid4()),
        email=email,
        password=_pwd.hash("secret123"),
        name="MFA",
        created_at=NOW.isoformat(),
    )
    db.add(user)
    db.commit()
    return user


def _service(db, now: datetime = NOW) -> MfaService:
    return MfaService(db, _pwd.verify, now_factory=lambda: now)


def _enable(db, user: User) -> tuple[MfaService, list[str], str]:
    service = _service(db)
    setup = service.start_enrollment(user.id, "secret123")
    code = pyotp.TOTP(setup["manual_key"]).at(NOW)
    result = service.confirm_enrollment(user.id, code)
    return service, result["recovery_codes"], setup["manual_key"]


def test_enrollment_encrypts_secret_and_returns_recovery_codes_once(db):
    user = _create_user(db)
    service = _service(db)

    setup = service.start_enrollment(user.id, "secret123")
    factor = db.execute(
        select(UserMfaFactor).where(UserMfaFactor.user_id == user.id)
    ).scalar_one()

    assert setup["manual_key"] not in factor.secret_ciphertext
    assert setup["otpauth_uri"].startswith("otpauth://totp/")
    result = service.confirm_enrollment(
        user.id,
        pyotp.TOTP(setup["manual_key"]).at(NOW),
    )

    assert len(result["recovery_codes"]) == 10
    assert len(set(result["recovery_codes"])) == 10
    assert service.get_status(user.id)["recovery_codes_remaining"] == 10
    db.refresh(user)
    assert user.auth_version == 1


def test_pending_enrollment_can_rotate_but_enabled_factor_cannot(db):
    user = _create_user(db)
    service = _service(db)

    first = service.start_enrollment(user.id, "secret123")
    second = service.start_enrollment(user.id, "secret123")
    assert first["manual_key"] != second["manual_key"]

    service.confirm_enrollment(
        user.id,
        pyotp.TOTP(second["manual_key"]).at(NOW),
    )
    with pytest.raises(MfaError, match="mfa.error.already_enabled"):
        service.start_enrollment(user.id, "secret123")


def test_login_challenge_requires_one_time_totp(db):
    user = _create_user(db)
    service, _, secret = _enable(db, user)
    later = NOW + timedelta(seconds=30)
    service = _service(db, later)
    code = pyotp.TOTP(secret).at(later)
    challenge = service.create_login_challenge(user.id)

    assert service.complete_login_challenge(challenge["token"], code) == user.id

    with pytest.raises(MfaError, match="mfa.error.invalid_challenge"):
        service.complete_login_challenge(challenge["token"], code)

    replay_challenge = service.create_login_challenge(user.id)
    with pytest.raises(MfaError, match="mfa.error.invalid_code"):
        service.complete_login_challenge(replay_challenge["token"], code)


def test_login_challenge_expires_and_exhausts_attempts(db):
    user = _create_user(db)
    service, _, _ = _enable(db, user)
    challenge = service.create_login_challenge(user.id)

    expired_service = _service(db, NOW + timedelta(minutes=6))
    with pytest.raises(MfaError, match="mfa.error.invalid_challenge"):
        expired_service.complete_login_challenge(challenge["token"], "000000")

    challenge = service.create_login_challenge(user.id)
    for _ in range(LOGIN_CHALLENGE_ATTEMPTS):
        with pytest.raises(MfaError, match="mfa.error.invalid_code"):
            service.complete_login_challenge(challenge["token"], "000000")
    with pytest.raises(MfaError, match="mfa.error.invalid_challenge"):
        service.complete_login_challenge(challenge["token"], "000000")


def test_recovery_code_is_single_use(db):
    user = _create_user(db)
    service, recovery_codes, _ = _enable(db, user)
    recovery_code = recovery_codes[0]

    first = service.create_login_challenge(user.id)
    assert service.complete_login_challenge(first["token"], recovery_code) == user.id

    second = service.create_login_challenge(user.id)
    with pytest.raises(MfaError, match="mfa.error.invalid_code"):
        service.complete_login_challenge(second["token"], recovery_code)
    assert service.get_status(user.id)["recovery_codes_remaining"] == 9


def test_regeneration_replaces_codes_and_disable_removes_mfa(db):
    user = _create_user(db)
    _, original_codes, secret = _enable(db, user)
    later = NOW + timedelta(seconds=30)
    service = _service(db, later)

    replacement_codes = service.regenerate_recovery_codes(
        user.id,
        "secret123",
        pyotp.TOTP(secret).at(later),
    )
    assert len(replacement_codes) == 10
    assert set(replacement_codes).isdisjoint(original_codes)

    service.disable(user.id, "secret123", replacement_codes[0])
    assert service.get_status(user.id)["enabled"] is False
    assert db.scalar(
        select(MfaRecoveryCode.id).where(MfaRecoveryCode.user_id == user.id)
    ) is None
    assert db.scalar(
        select(MfaLoginChallenge.id).where(MfaLoginChallenge.user_id == user.id)
    ) is None
    db.refresh(user)
    assert user.auth_version == 2


def test_sensitive_actions_reject_wrong_password_or_code(db):
    user = _create_user(db)
    service, _, _ = _enable(db, user)

    with pytest.raises(MfaError, match="auth.error.current_password_incorrect"):
        service.disable(user.id, "wrong", "000000")
    with pytest.raises(MfaError, match="mfa.error.invalid_code"):
        service.disable(user.id, "secret123", "000000")
