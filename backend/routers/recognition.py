"""Router for trade-record recognition (file/image upload -> parsed trades)."""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from api_response import error, success
from auth_dependency import get_current_user
from db import get_db
from i18n import get_lang, t
from services.billing import BillingModule, RECOGNITION_UNIT_COST
from services.recognition import (
    SUPPORTED_FILE_TYPES,
    SUPPORTED_IMAGE_TYPES,
    parse_file,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recognition", tags=["recognition"])

_ALL_SUPPORTED = SUPPORTED_IMAGE_TYPES | SUPPORTED_FILE_TYPES
_SUPPORTED_EXTENSIONS = {".csv", ".json", ".xlsx", ".png", ".jpg", ".jpeg", ".webp"}


@router.post("/parse")
async def parse(
    file: UploadFile = File(...),
    request: Request = None,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    lang = get_lang(request) if request else "zh"

    # Validate content type or fall back to extension check
    content_type = file.content_type or "application/octet-stream"
    if content_type not in _ALL_SUPPORTED:
        # Fall back: check filename extension
        filename = file.filename or ""
        ext = ""
        dot_idx = filename.rfind(".")
        if dot_idx >= 0:
            ext = filename[dot_idx:].lower()
        if ext not in _SUPPORTED_EXTENSIONS:
            return error(
                message=t("recognition.error", lang),
                code=400,
                status_code=400,
            )

    BillingModule(session).require(
        user_id,
        "recognition.parse",
        units=RECOGNITION_UNIT_COST,
        request_id=(request.headers.get("X-Request-ID") if request else None) or str(uuid4()),
    )
    try:
        file_bytes = await file.read()
        result = await parse_file(
            file_bytes=file_bytes,
            content_type=content_type,
            filename=file.filename or "",
            lang=lang,
        )
        return success(result)
    except ValueError as exc:
        logger.warning("Recognition rejected file: %s", exc)
        return error(message=t("recognition.error", lang), code=400, status_code=400)
    except Exception as exc:
        logger.exception("Recognition failed: %s", exc)
        return error(message=t("recognition.error", lang), code=500, status_code=500)
