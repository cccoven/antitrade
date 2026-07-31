from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api_response import error, success
from auth_dependency import get_current_user, get_current_user_header_or_query
from db import get_db
from i18n import t
from services.uploads import SUPPORTED_IMAGE_TYPES, UploadService

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


class ImageAnnotationRequest(BaseModel):
    x_ratio: float = Field(ge=0, le=1)
    y_ratio: float = Field(ge=0, le=1)
    body: str = Field(min_length=1, max_length=4000)


class ReplaceImageAnnotationsRequest(BaseModel):
    items: list[ImageAnnotationRequest] = Field(max_length=50)


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    svc = UploadService(session)
    try:
        asset = await svc.create_asset(file, user_id=user_id)
    except ValueError as exc:
        message_key = {
            "unsupported_type": "upload.error.unsupported_type",
            "empty_file": "upload.error.empty_file",
            "file_too_large": "upload.error.file_too_large",
            "invalid_image": "upload.error.invalid_image",
        }.get(str(exc), "upload.error.failed")
        return error(message=t(message_key), code=400, status_code=400)
    return success(asset)


@router.get("/{asset_id}/annotations")
async def list_image_annotations(
    asset_id: str,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    svc = UploadService(session)
    try:
        items = svc.list_annotations(asset_id, user_id)
    except LookupError:
        return error(message="File not found", code=404, status_code=404)
    except ValueError:
        return error(
            message="Annotations require an image",
            code=400,
            status_code=400,
        )
    return success({"items": items})


@router.put("/{asset_id}/annotations")
async def replace_image_annotations(
    asset_id: str,
    req: ReplaceImageAnnotationsRequest,
    user_id: str = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    items = [
        {**item.model_dump(), "body": item.body.strip()}
        for item in req.items
    ]
    if any(not item["body"] for item in items):
        return error(
            message="Annotation note is required",
            code=400,
            status_code=400,
        )
    svc = UploadService(session)
    try:
        saved = svc.replace_annotations(asset_id, user_id, items)
    except LookupError:
        return error(message="File not found", code=404, status_code=404)
    except ValueError:
        return error(
            message="Annotations require an image",
            code=400,
            status_code=400,
        )
    return success({"items": saved})


@router.get("/{asset_id}")
async def get_uploaded_file(
    asset_id: str,
    user_id: str = Depends(get_current_user_header_or_query),
    session: Session = Depends(get_db),
):
    svc = UploadService(session)
    asset = svc.get_asset(asset_id, user_id=user_id)
    if asset is None:
        return error(message="File not found", code=404, status_code=404)
    path = Path(asset.file_path)
    if not path.exists():
        return error(message="File not found", code=404, status_code=404)
    return FileResponse(
        path,
        media_type=asset.mime_type,
        filename=asset.original_name,
        content_disposition_type="inline" if asset.mime_type in SUPPORTED_IMAGE_TYPES else "attachment",
    )
