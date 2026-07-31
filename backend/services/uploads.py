import imghdr
import os
import shutil
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import delete, select

from models import ImageAnnotation, UploadedAsset


SUPPORTED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
SUPPORTED_ATTACHMENT_TYPES = {
    "application/pdf": (".pdf",),
    "text/plain": (".txt",),
    "text/markdown": (".md", ".markdown"),
    "text/csv": (".csv",),
    "application/json": (".json",),
    "application/zip": (".zip",),
    "application/msword": (".doc",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (".docx",),
    "application/vnd.ms-excel": (".xls",),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (".xlsx",),
    "application/vnd.ms-powerpoint": (".ppt",),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (".pptx",),
}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
READ_CHUNK_BYTES = 1024 * 1024


@dataclass
class StoredAsset:
    id: str
    user_id: str
    file_path: str
    original_name: str | None
    mime_type: str
    width: int | None
    height: int | None
    size_bytes: int
    created_at: str


def _upload_root() -> Path:
    return Path(os.environ.get("UPLOAD_DIR", "uploads")).resolve()


def delete_user_uploads(user_id: str) -> None:
    root = _upload_root()
    user_dir = (root / user_id).resolve()
    try:
        user_dir.relative_to(root)
    except ValueError:
        return
    shutil.rmtree(user_dir, ignore_errors=True)


def _detect_dimensions(data: bytes, mime_type: str) -> tuple[int | None, int | None]:
    if mime_type == "image/png" and len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    if mime_type == "image/jpeg":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            i += 2
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height = int.from_bytes(data[i + 3:i + 5], "big")
                width = int.from_bytes(data[i + 5:i + 7], "big")
                return width, height
            if i + 2 > len(data):
                break
            segment_len = int.from_bytes(data[i:i + 2], "big")
            i += segment_len
    if mime_type == "image/webp" and len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if data[12:16] == b"VP8X" and len(data) >= 30:
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return width, height
    return None, None


async def _read_upload_bounded(file: UploadFile) -> bytes:
    data = bytearray()
    while True:
        chunk = await file.read(READ_CHUNK_BYTES)
        if not chunk:
            break
        if len(data) + len(chunk) > MAX_UPLOAD_BYTES:
            raise ValueError("file_too_large")
        data.extend(chunk)
    return bytes(data)


class UploadService:
    def __init__(self, session: Session):
        self.session = session

    async def create_asset(self, file: UploadFile, user_id: str) -> dict:
        mime_type = file.content_type or ""
        if mime_type not in SUPPORTED_IMAGE_TYPES and mime_type not in SUPPORTED_ATTACHMENT_TYPES:
            raise ValueError("unsupported_type")

        data = await _read_upload_bounded(file)
        if not data:
            raise ValueError("empty_file")

        if mime_type in SUPPORTED_IMAGE_TYPES:
            detected = imghdr.what(None, data)
            if mime_type == "image/png" and detected != "png":
                raise ValueError("invalid_image")
            if mime_type == "image/jpeg" and detected not in {"jpeg", "jpg"}:
                raise ValueError("invalid_image")
            if mime_type == "image/webp" and not (len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
                raise ValueError("invalid_image")

        asset_id = str(uuid4())
        if mime_type in SUPPORTED_IMAGE_TYPES:
            ext = SUPPORTED_IMAGE_TYPES[mime_type]
        else:
            allowed_extensions = SUPPORTED_ATTACHMENT_TYPES[mime_type]
            original_extension = Path(file.filename or "").suffix.lower()
            ext = original_extension if original_extension in allowed_extensions else allowed_extensions[0]
        root = _upload_root()
        user_dir = root / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        path = user_dir / f"{asset_id}{ext}"
        path.write_bytes(data)

        width, height = _detect_dimensions(data, mime_type)
        created_at = datetime.now(timezone.utc).isoformat()
        try:
            self.session.add(UploadedAsset(
                id=asset_id,
                user_id=user_id,
                file_path=str(path),
                original_name=file.filename,
                mime_type=mime_type,
                width=width,
                height=height,
                size_bytes=len(data),
                created_at=created_at,
            ))
            self.session.commit()
        except Exception:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            raise
        return self.asset_to_response(self.get_asset(asset_id, user_id))

    def get_asset(self, asset_id: str, user_id: str) -> StoredAsset | None:
        row = self.session.execute(
            select(UploadedAsset).where(
                UploadedAsset.id == asset_id,
                UploadedAsset.user_id == user_id,
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return StoredAsset(
            id=row.id,
            user_id=row.user_id,
            file_path=row.file_path,
            original_name=row.original_name,
            mime_type=row.mime_type,
            width=row.width,
            height=row.height,
            size_bytes=row.size_bytes,
            created_at=row.created_at,
        )

    def list_annotations(self, asset_id: str, user_id: str) -> list[dict]:
        self._validate_annotation_asset(asset_id, user_id)
        rows = self.session.execute(
            select(ImageAnnotation)
            .where(ImageAnnotation.asset_id == asset_id)
            .order_by(
                ImageAnnotation.sort_order.asc(),
                ImageAnnotation.created_at.asc(),
            )
        ).scalars().all()
        return [self.annotation_to_response(row) for row in rows]

    def replace_annotations(
        self,
        asset_id: str,
        user_id: str,
        items: list[dict],
    ) -> list[dict]:
        self._validate_annotation_asset(asset_id, user_id)
        self.session.execute(
            delete(ImageAnnotation).where(ImageAnnotation.asset_id == asset_id)
        )
        now = datetime.now(timezone.utc).isoformat()
        for sort_order, item in enumerate(items):
            self.session.add(
                ImageAnnotation(
                    id=str(uuid4()),
                    asset_id=asset_id,
                    x_ratio=item["x_ratio"],
                    y_ratio=item["y_ratio"],
                    body=item["body"],
                    sort_order=sort_order,
                    created_at=now,
                    updated_at=now,
                )
            )
        self.session.commit()
        return self.list_annotations(asset_id, user_id)

    def _validate_annotation_asset(self, asset_id: str, user_id: str) -> None:
        asset = self.get_asset(asset_id, user_id)
        if asset is None:
            raise LookupError("asset_not_found")
        if asset.mime_type not in SUPPORTED_IMAGE_TYPES:
            raise ValueError("annotations_require_image")

    @staticmethod
    def annotation_to_response(row: ImageAnnotation) -> dict:
        return {
            "id": row.id,
            "asset_id": row.asset_id,
            "x_ratio": row.x_ratio,
            "y_ratio": row.y_ratio,
            "body": row.body,
            "sort_order": row.sort_order,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def asset_to_response(asset: StoredAsset | None) -> dict | None:
        if asset is None:
            return None
        return {
            "id": asset.id,
            "url": f"/api/uploads/{asset.id}",
            "original_name": asset.original_name,
            "mime_type": asset.mime_type,
            "width": asset.width,
            "height": asset.height,
            "size_bytes": asset.size_bytes,
            "created_at": asset.created_at,
        }
