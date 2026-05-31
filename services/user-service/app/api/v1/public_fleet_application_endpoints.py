from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_publisher, get_s3_client
from app.repositories.fleet_application_repo import FleetApplicationRepository
from app.repositories.fleet_document_repo import FleetDocumentRepository
from app.repositories.fleet_repo import FleetRepository
from app.schemas.fleet_application import FleetApplicationPublicResponse
from app.services.fleet_application_service import FleetApplicationService
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.responses import StandardResponse
from mediride_common.storage.s3_client import S3StorageClient

router = APIRouter()


def _get_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> FleetApplicationService:
    return FleetApplicationService(
        app_repo=FleetApplicationRepository(session),
        doc_repo=FleetDocumentRepository(session),
        fleet_repo=FleetRepository(session),
        publisher=publisher,
    )


@router.post(
    "/public/fleet/apply",
    response_model=StandardResponse[FleetApplicationPublicResponse],
    status_code=201,
)
async def submit_fleet_application(
    # Company Information
    company_name: str = Form(...),
    business_registration_number: str = Form(...),
    years_in_operation: int = Form(..., ge=0),
    street_address: str = Form(...),
    city: str = Form(...),
    province: str = Form(...),
    postal_code: str = Form(...),
    # Primary Contact Information
    contact_person: str = Form(...),
    contact_title: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    alternate_phone: str | None = Form(None),
    # Fleet Composition
    fleet_size: int = Form(..., ge=1),
    average_vehicle_age: int | None = Form(None),
    wheelchair_accessible_count: int = Form(0),
    stretcher_accessible_count: int = Form(0),
    ambulatory_vehicle_count: int = Form(0),
    # Insurance & Compliance
    insurance_provider: str = Form(...),
    policy_number: str = Form(...),
    liability_coverage_amount: str = Form(...),
    # Additional Information
    service_areas: str = Form(...),
    healthcare_contracts: str | None = Form(None),
    additional_info: str | None = Form(None),
    # Consent
    consent_accuracy: bool = Form(...),
    consent_compliance: bool = Form(...),
    consent_contact: bool = Form(...),
    # Documents (all optional — uploaded when available)
    certificate_of_insurance: UploadFile | None = File(None),
    business_registration_doc: UploadFile | None = File(None),
    vehicle_registration_doc: UploadFile | None = File(None),
    driver_certifications_doc: UploadFile | None = File(None),
    safety_compliance_doc: UploadFile | None = File(None),
    # Dependencies
    service: FleetApplicationService = Depends(_get_service),
    s3_client: S3StorageClient = Depends(get_s3_client),
):
    """Public endpoint for fleet partners to submit an application with documents.
    No authentication required. Accepts multipart/form-data."""

    if not (consent_accuracy and consent_compliance and consent_contact):
        raise HTTPException(
            status_code=422,
            detail="All consent checkboxes must be accepted to submit an application.",
        )

    # Create the application
    application = await service.create_public_application(
        company_name=company_name,
        business_registration_number=business_registration_number,
        years_in_operation=years_in_operation,
        street_address=street_address,
        city=city,
        province=province,
        postal_code=postal_code,
        contact_person=contact_person,
        contact_title=contact_title,
        email=email,
        phone=phone,
        alternate_phone=alternate_phone,
        fleet_size=fleet_size,
        average_vehicle_age=average_vehicle_age,
        wheelchair_accessible_count=wheelchair_accessible_count,
        stretcher_accessible_count=stretcher_accessible_count,
        ambulatory_vehicle_count=ambulatory_vehicle_count,
        insurance_provider=insurance_provider,
        policy_number=policy_number,
        liability_coverage_amount=liability_coverage_amount,
        service_areas=service_areas,
        healthcare_contracts=healthcare_contracts,
        additional_info=additional_info,
        consent_accuracy=consent_accuracy,
        consent_compliance=consent_compliance,
        consent_contact=consent_contact,
    )

    # Upload any attached documents
    doc_files = [
        ("certificate_of_insurance", certificate_of_insurance),
        ("business_registration", business_registration_doc),
        ("vehicle_registration", vehicle_registration_doc),
        ("driver_certifications", driver_certifications_doc),
        ("safety_compliance", safety_compliance_doc),
    ]

    for doc_type, file in doc_files:
        if file is None or file.filename is None or file.filename == "":
            continue

        file_data = await file.read()
        if not file_data:
            continue

        file_key = f"fleet-applications/{application.id}/{doc_type}/{file.filename}"

        await s3_client.upload_file(
            bucket=settings.S3_BUCKET_DOCUMENTS,
            key=file_key,
            data=file_data,
            content_type=file.content_type or "application/octet-stream",
        )

        await service.upload_document(
            app_id=application.id,
            document_type=doc_type,
            file_key=file_key,
            file_name=file.filename,
            file_size=len(file_data),
            mime_type=file.content_type or "application/octet-stream",
        )

    return StandardResponse(
        data=FleetApplicationPublicResponse.model_validate(application),
        message="Fleet partner application submitted successfully",
    )
