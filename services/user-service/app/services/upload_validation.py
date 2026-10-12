"""Checks for files uploaded by users.

The type is decided from the file's own first bytes, never from the filename
or the content type the client claims, and files are stored under a server
generated name. This stops someone storing a script or an oversized file under
a harmless-looking name, and stops filenames being used to write to other
people's folders.
"""

import re
from dataclasses import dataclass
from uuid import uuid4

from mediride_common.exceptions import ValidationError

MB = 1024 * 1024
IMAGE_MAX_BYTES = 10 * MB
DOCUMENT_MAX_BYTES = 10 * MB


@dataclass(frozen=True)
class CheckedUpload:
    content_type: str
    extension: str

    def new_name(self) -> str:
        return f"{uuid4().hex}.{self.extension}"


def sniff_type(data: bytes) -> CheckedUpload | None:
    if data.startswith(b"\xff\xd8\xff"):
        return CheckedUpload("image/jpeg", "jpg")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return CheckedUpload("image/png", "png")
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return CheckedUpload("image/webp", "webp")
    if data[4:8] == b"ftyp" and data[8:12] in (b"heic", b"heix", b"mif1", b"heif"):
        return CheckedUpload("image/heic", "heic")
    if data.startswith(b"%PDF-"):
        return CheckedUpload("application/pdf", "pdf")
    return None


def check_upload(data: bytes, *, allow_pdf: bool, max_bytes: int) -> CheckedUpload:
    if not data:
        raise ValidationError("The uploaded file is empty")
    if len(data) > max_bytes:
        raise ValidationError(f"The file is too large (limit {max_bytes // MB} MB)")
    checked = sniff_type(data)
    if checked is None or (checked.content_type == "application/pdf" and not allow_pdf):
        allowed = "JPEG, PNG, WebP, HEIC or PDF" if allow_pdf else "JPEG, PNG, WebP or HEIC"
        raise ValidationError(f"Unsupported file type. Allowed: {allowed}")
    return checked


def safe_display_name(filename: str | None) -> str:
    """A harmless name for showing in lists (never used as a storage key)."""
    name = (filename or "file").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")
    return name[:100] or "file"
