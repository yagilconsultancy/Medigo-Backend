from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


class FleetApplicationCreate(BaseModel):
    company_name: str = Field(..., max_length=255)
    contact_person: str = Field(..., max_length=255)
    email: str = Field(..., max_length=255)
    phone: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=100)
    province: str | None = Field(None, max_length=50)
    fleet_size: int = Field(0, ge=0)
    driver_count: int = Field(0, ge=0)
    description: str | None = None


class FleetApplicationPublicCreate(BaseModel):
    """Public fleet partner application form — no authentication required."""

    # Company Information
    company_name: str = Field(..., max_length=255, description="Legal Company Name")
    business_registration_number: str = Field(..., max_length=100)
    years_in_operation: int = Field(..., ge=0)
    street_address: str = Field(..., max_length=500)
    city: str = Field(..., max_length=100)
    province: str = Field(..., max_length=50)
    postal_code: str = Field(..., max_length=20)

    # Primary Contact Information
    contact_person: str = Field(..., max_length=255, description="Full Name")
    contact_title: str = Field(..., max_length=255, description="Title / Position")
    email: EmailStr = Field(..., description="Email Address")
    phone: str = Field(..., max_length=20, description="Phone Number")
    alternate_phone: str | None = Field(None, max_length=20)

    # Fleet Composition
    fleet_size: int = Field(..., ge=1, description="Total Number of Vehicles")
    average_vehicle_age: int | None = Field(None, ge=0, description="Average Vehicle Age (years)")
    wheelchair_accessible_count: int = Field(0, ge=0)
    stretcher_accessible_count: int = Field(0, ge=0)
    ambulatory_vehicle_count: int = Field(0, ge=0)

    # Insurance & Compliance
    insurance_provider: str = Field(..., max_length=255)
    policy_number: str = Field(..., max_length=100)
    liability_coverage_amount: str = Field(..., max_length=50, description="Minimum $2,000,000 required")

    # Additional Information
    service_areas: str = Field(..., description="Cities, regions, or postal code areas currently served")
    healthcare_contracts: str | None = Field(None, description="Existing contracts with hospitals, clinics, etc.")
    additional_info: str | None = Field(None)

    # Consent (all required to be True)
    consent_accuracy: bool = Field(..., description="Confirm all information is accurate")
    consent_compliance: bool = Field(..., description="Acknowledge compliance with operational standards")
    consent_contact: bool = Field(..., description="Consent to be contacted regarding this application")


class ApproveApplicationRequest(BaseModel):
    notes: str | None = None


class RejectApplicationRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class RequestInfoRequest(BaseModel):
    message: str = Field(..., min_length=1)


class FleetDocumentResponse(BaseModel):
    id: UUID
    document_type: str
    file_key: str
    file_name: str
    file_size: int
    mime_type: str
    file_url: str | None = None
    verification_status: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def build_file_url(self) -> "FleetDocumentResponse":
        if self.file_key and not self.file_url:
            from app.config import settings

            self.file_url = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET_DOCUMENTS}/{self.file_key}"
        return self


class FleetApplicationResponse(BaseModel):
    id: UUID
    company_name: str
    business_registration_number: str | None = None
    years_in_operation: int | None = None
    street_address: str | None = None
    contact_person: str
    contact_title: str | None = None
    email: str
    phone: str | None = None
    alternate_phone: str | None = None
    city: str | None = None
    province: str | None = None
    postal_code: str | None = None
    fleet_size: int
    average_vehicle_age: int | None = None
    wheelchair_accessible_count: int = 0
    stretcher_accessible_count: int = 0
    ambulatory_vehicle_count: int = 0
    insurance_provider: str | None = None
    policy_number: str | None = None
    liability_coverage_amount: str | None = None
    service_areas: str | None = None
    healthcare_contracts: str | None = None
    additional_info: str | None = None
    consent_accuracy: bool = False
    consent_compliance: bool = False
    consent_contact: bool = False
    driver_count: int = 0
    description: str | None = None
    status: str
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    rejection_reason: str | None = None
    info_request_message: str | None = None
    business_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    documents: list[FleetDocumentResponse] = []

    model_config = {"from_attributes": True}


class FleetApplicationPublicResponse(BaseModel):
    """Minimal response for public submissions — no internal fields exposed."""

    id: UUID
    company_name: str
    email: str
    status: str
    created_at: datetime
    message: str = "Your fleet partner application has been submitted successfully. We will review your application and get back to you."

    model_config = {"from_attributes": True}


class FleetApplicationKPIs(BaseModel):
    total_applications: int
    pending_review: int
    approved: int
    rejected: int
