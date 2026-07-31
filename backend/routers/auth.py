"""Auth router — registration, login, profile, and password changes."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api_response import success, error
from auth_dependency import get_current_user
from config import GOOGLE_CLIENT_ID
from db import get_db
from i18n import get_lang, t
from services.auth import AuthService
from services.google_auth import GoogleAuthError, GoogleAuthUnavailableError
from services.mfa import MfaConfigurationError, MfaError

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class GoogleLoginRequest(BaseModel):
    credential: str


class UpdateProfileRequest(BaseModel):
    name: str


class ChangePasswordRequest(BaseModel):
    current_password: str | None = None
    new_password: str


class DeleteAccountRequest(BaseModel):
    current_password: str


class MfaSetupStartRequest(BaseModel):
    current_password: str


class MfaCodeRequest(BaseModel):
    code: str


class MfaLoginVerifyRequest(BaseModel):
    challenge_token: str
    code: str


class MfaSensitiveActionRequest(BaseModel):
    current_password: str
    code: str


@router.post("/register")
async def register(req: RegisterRequest, session: Session = Depends(get_db)):
    svc = AuthService(session)
    try:
        result = svc.register(email=req.email, password=req.password, name=req.name)
        return success(result)
    except ValueError as e:
        return error(message=str(e), code=400, status_code=400)


@router.post("/login")
async def login(req: LoginRequest, session: Session = Depends(get_db)):
    svc = AuthService(session)
    try:
        result = svc.login(email=req.email, password=req.password)
        return success(result)
    except ValueError as e:
        return error(message=str(e), code=401, status_code=401)


@router.get("/google/config")
async def google_config():
    return success({
        "enabled": bool(GOOGLE_CLIENT_ID),
        "client_id": GOOGLE_CLIENT_ID or None,
    })


@router.post("/google")
async def google_login(
    req: GoogleLoginRequest,
    session: Session = Depends(get_db),
):
    try:
        return success(AuthService(session).login_with_google(req.credential))
    except GoogleAuthUnavailableError as exc:
        return error(message=str(exc), code=503, status_code=503)
    except GoogleAuthError as exc:
        return error(message=str(exc), code=401, status_code=401)


@router.get("/me")
async def me(user_id: str = Depends(get_current_user), session: Session = Depends(get_db)):
    svc = AuthService(session)
    user = svc.get_user(user_id)
    if not user:
        return error(message="User not found", code=404, status_code=404)
    return success(user)


@router.put("/profile")
async def update_profile(req: UpdateProfileRequest, user_id: str = Depends(get_current_user), session: Session = Depends(get_db)):
    svc = AuthService(session)
    try:
        user = svc.update_profile(user_id, req.name)
        return success(user)
    except ValueError as e:
        return error(message=str(e), code=400, status_code=400)


@router.put("/password")
async def change_password(
    req: ChangePasswordRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        result = AuthService(session).change_password(
            user_id,
            req.current_password,
            req.new_password,
        )
        return success(result)
    except ValueError as exc:
        return error(
            message=t(str(exc), get_lang(request)),
            code=400,
            status_code=400,
        )


@router.post("/mfa/login/verify")
async def verify_mfa_login(
    req: MfaLoginVerifyRequest,
    request: Request,
    session: Session = Depends(get_db),
):
    try:
        result = AuthService(session).complete_mfa_login(
            req.challenge_token,
            req.code,
        )
        return success(result)
    except MfaError as exc:
        return error(
            message=t(str(exc), get_lang(request)),
            code=401,
            status_code=401,
        )
    except MfaConfigurationError:
        return error(
            message=t("mfa.error.unavailable", get_lang(request)),
            code=503,
            status_code=503,
        )


@router.get("/mfa/status")
async def mfa_status(
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    return success(AuthService(session).get_mfa_status(user_id))


@router.post("/mfa/setup/start")
async def start_mfa_setup(
    req: MfaSetupStartRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return success(
            AuthService(session).start_mfa_enrollment(
                user_id,
                req.current_password,
            )
        )
    except MfaError as exc:
        return error(
            message=t(str(exc), get_lang(request)),
            code=400,
            status_code=400,
        )
    except MfaConfigurationError:
        return error(
            message=t("mfa.error.unavailable", get_lang(request)),
            code=503,
            status_code=503,
        )


@router.post("/mfa/setup/confirm")
async def confirm_mfa_setup(
    req: MfaCodeRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return success(
            AuthService(session).confirm_mfa_enrollment(user_id, req.code)
        )
    except MfaError as exc:
        return error(
            message=t(str(exc), get_lang(request)),
            code=400,
            status_code=400,
        )
    except MfaConfigurationError:
        return error(
            message=t("mfa.error.unavailable", get_lang(request)),
            code=503,
            status_code=503,
        )


@router.post("/mfa/disable")
async def disable_mfa(
    req: MfaSensitiveActionRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        return success(
            AuthService(session).disable_mfa(
                user_id,
                req.current_password,
                req.code,
            )
        )
    except MfaError as exc:
        return error(
            message=t(str(exc), get_lang(request)),
            code=400,
            status_code=400,
        )
    except MfaConfigurationError:
        return error(
            message=t("mfa.error.unavailable", get_lang(request)),
            code=503,
            status_code=503,
        )


@router.post("/mfa/recovery-codes/regenerate")
async def regenerate_mfa_recovery_codes(
    req: MfaSensitiveActionRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        recovery_codes = AuthService(session).regenerate_mfa_recovery_codes(
            user_id,
            req.current_password,
            req.code,
        )
        return success({"recovery_codes": recovery_codes})
    except MfaError as exc:
        return error(
            message=t(str(exc), get_lang(request)),
            code=400,
            status_code=400,
        )
    except MfaConfigurationError:
        return error(
            message=t("mfa.error.unavailable", get_lang(request)),
            code=503,
            status_code=503,
        )


@router.delete("/account")
async def delete_account(
    req: DeleteAccountRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    try:
        AuthService(session).delete_account(user_id, req.current_password)
        return success({"deleted": True})
    except ValueError as exc:
        return error(
            message=t(str(exc), get_lang(request)),
            code=400,
            status_code=400,
        )
