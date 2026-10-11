import pytest

from app.services.upload_validation import (
    IMAGE_MAX_BYTES,
    check_upload,
    safe_display_name,
)
from mediride_common.exceptions import ValidationError

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
PDF = b"%PDF-1.7\n" + b"0" * 100
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"0" * 50
HEIC = b"\x00\x00\x00\x18ftypheic" + b"0" * 50
SCRIPT = b"<script>alert(1)</script>"
EXE = b"MZ\x90\x00" + b"0" * 100


def test_accepts_real_images_and_names_them_safely():
    for data, ctype, ext in [
        (JPEG, "image/jpeg", "jpg"),
        (PNG, "image/png", "png"),
        (WEBP, "image/webp", "webp"),
        (HEIC, "image/heic", "heic"),
    ]:
        checked = check_upload(data, allow_pdf=False, max_bytes=IMAGE_MAX_BYTES)
        assert checked.content_type == ctype
        name = checked.new_name()
        assert name.endswith("." + ext)
        assert "/" not in name and ".." not in name


def test_pdf_only_where_allowed():
    assert check_upload(PDF, allow_pdf=True, max_bytes=1000).content_type == "application/pdf"
    with pytest.raises(ValidationError):
        check_upload(PDF, allow_pdf=False, max_bytes=1000)


@pytest.mark.parametrize("data", [SCRIPT, EXE, b"GIF89a....", b"random text"])
def test_rejects_other_types_even_if_client_says_image(data):
    with pytest.raises(ValidationError):
        check_upload(data, allow_pdf=True, max_bytes=1000)


def test_rejects_empty_and_oversized():
    with pytest.raises(ValidationError):
        check_upload(b"", allow_pdf=True, max_bytes=1000)
    with pytest.raises(ValidationError):
        check_upload(JPEG + b"0" * 2000, allow_pdf=True, max_bytes=1000)


def test_display_name_cannot_carry_a_path():
    assert safe_display_name("../../etc/passwd") == "passwd"
    assert safe_display_name("C:\\evil\\doc.pdf") == "doc.pdf"
    assert safe_display_name(None) == "file"
    assert "<" not in safe_display_name("<img onerror=x>.pdf")
