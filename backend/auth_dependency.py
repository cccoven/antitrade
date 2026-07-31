"""FastAPI dependency for extracting authenticated user from JWT."""
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session

from db import get_db


def _verify(token: str, session: Session) -> str:
    from services.auth import AuthService
    svc = AuthService(session)
    user_id = svc.verify_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = svc.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user_id


async def get_current_user(request: Request, session: Session = Depends(get_db)) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return _verify(auth_header[7:], session)


async def get_current_user_header_or_query(request: Request, session: Session = Depends(get_db)) -> str:
    """Fallback for routes loaded via <img>/<a> tags that can't set headers.

    Accepts the JWT either via the Authorization header (preferred) or a
    `?token=` query parameter. The query-param form leaks the token in logs,
    so use it only for asset endpoints that can't use headers.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return _verify(auth_header[7:], session)
    token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return _verify(token, session)
