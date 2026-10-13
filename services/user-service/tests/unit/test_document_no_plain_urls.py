from datetime import date, datetime, timezone
from uuid import uuid4

from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.schemas.vehicle_document import (
    VehicleDocumentResponse,
    VehicleDocumentUploadResponse,
)

NOW = datetime.now(timezone.utc)
KEY = "documents/some-user/id-front.jpg"


def test_rider_document_upload_response_has_no_plain_address():
    r = DocumentUploadResponse(
        id=uuid4(), document_type="government_id_front", file_key=KEY,
        file_name="id.jpg", verification_status="pending", created_at=NOW,
    )
    assert r.file_url is None


def test_rider_document_response_has_no_plain_address():
    r = DocumentResponse(
        id=uuid4(), document_type="government_id_front", file_key=KEY,
        file_name="id.jpg", file_size=10, mime_type="image/jpeg",
        verification_status="pending", created_at=NOW, updated_at=NOW,
    )
    assert r.file_url is None


def test_signed_link_can_still_be_set_on_document_response():
    r = DocumentResponse(
        id=uuid4(), document_type="government_id_front", file_key=KEY,
        file_name="id.jpg", file_size=10, mime_type="image/jpeg",
        verification_status="pending", created_at=NOW, updated_at=NOW,
        presigned_url="https://signed.example/x?sig=1",
    )
    assert r.presigned_url.startswith("https://signed.example/")
    assert r.file_url is None


def test_vehicle_document_responses_have_no_plain_address():
    full = VehicleDocumentResponse(
        id=uuid4(), vehicle_id=uuid4(), document_type="insurance", file_key=KEY,
        file_name="a.pdf", file_size=10, mime_type="application/pdf",
        status="valid", uploaded_by=uuid4(), created_at=NOW, updated_at=NOW,
        expires_at=date(2030, 1, 1),
    )
    up = VehicleDocumentUploadResponse(
        id=uuid4(), vehicle_id=uuid4(), document_type="insurance", file_key=KEY,
        file_name="a.pdf", status="valid", created_at=NOW,
    )
    assert full.file_url is None
    assert up.file_url is None
