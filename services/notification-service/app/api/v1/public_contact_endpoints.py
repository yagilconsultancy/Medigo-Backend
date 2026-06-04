from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.contact import ContactMessageRequest, ContactMessageResponse
from app.services.contact_message_service import ContactMessageService
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> ContactMessageService:
    return ContactMessageService(session)


@router.post("/contact", response_model=StandardResponse[ContactMessageResponse])
async def submit_contact_message(
    body: ContactMessageRequest,
    service: ContactMessageService = Depends(_get_service),
):
    """Public endpoint for unauthenticated users to submit a contact message."""
    msg = await service.submit_message(
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        service_type=body.service_type,
        message=body.message,
    )
    return StandardResponse(
        data=ContactMessageResponse.model_validate(msg),
        message="Your message has been sent successfully. We typically respond within 24 hours.",
    )
