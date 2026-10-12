from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.config import settings
from app.schemas.fleet_application import FleetApplicationResponse, FleetDocumentResponse
from app.services.document_links import sign_applications, sign_fleet_documents


def _doc(key="fleet-applications/abc/business_registration/My File.pdf"):
    return FleetDocumentResponse(
        id=uuid4(),
        document_type="business_registration",
        file_key=key,
        file_name="My File.pdf",
        file_size=10,
        mime_type="application/pdf",
        verification_status="pending",
        created_at=datetime.now(timezone.utc),
    )


def _s3():
    s3 = MagicMock()
    s3.generate_presigned_url = AsyncMock(side_effect=lambda **kw: f"https://signed.example/{kw['key']}?sig=1")
    return s3


def test_document_response_no_longer_carries_a_public_address():
    """The plain bucket address must never be built from the file key."""
    assert _doc().file_url is None


@pytest.mark.asyncio
async def test_sign_fleet_documents_sets_a_signed_link_with_one_hour_lifetime():
    s3 = _s3()
    docs = [_doc(), _doc("fleet-documents/x/licence/a.pdf")]

    await sign_fleet_documents(s3, docs)

    assert docs[0].file_url.startswith("https://signed.example/fleet-applications/")
    assert docs[1].file_url.startswith("https://signed.example/fleet-documents/")
    first = s3.generate_presigned_url.await_args_list[0].kwargs
    assert first["bucket"] == settings.S3_BUCKET_DOCUMENTS
    assert first["expires_in"] == 3600


@pytest.mark.asyncio
async def test_sign_applications_handles_one_or_many_responses():
    s3 = _s3()
    now = datetime.now(timezone.utc)

    def app_resp():
        return FleetApplicationResponse(
            id=uuid4(),
            company_name="Acme Transport",
            email="a@example.com",
            contact_person="A",
            fleet_size=3,
            status="pending",
            created_at=now,
            updated_at=now,
            documents=[_doc()],
        )

    one = app_resp()
    many = [app_resp(), app_resp()]

    await sign_applications(s3, one)
    await sign_applications(s3, many)

    assert one.documents[0].file_url.startswith("https://signed.example/")
    assert all(a.documents[0].file_url.startswith("https://signed.example/") for a in many)


@pytest.mark.asyncio
async def test_sign_fleet_documents_ignores_empty_lists():
    s3 = _s3()
    await sign_fleet_documents(s3, [])
    await sign_fleet_documents(s3, None)
    s3.generate_presigned_url.assert_not_awaited()
