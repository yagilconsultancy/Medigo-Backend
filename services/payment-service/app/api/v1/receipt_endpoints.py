from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.ride_service_client import RideServiceClient
from app.config import settings
from app.dependencies import get_db
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.payment_method_repo import PaymentMethodRepository
from app.schemas.receipt import ReceiptResponse
from app.services.receipt_service import ReceiptService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_receipt_service(session: AsyncSession = Depends(get_db)) -> ReceiptService:
    return ReceiptService(
        fare_repo=FareBreakdownRepository(session),
        pm_repo=PaymentMethodRepository(session),
        ride_client=RideServiceClient(settings.RIDE_SERVICE_URL),
    )


@router.get("/{ride_id}", response_model=StandardResponse[ReceiptResponse])
async def get_receipt(
    ride_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.DRIVER, UserRole.RIDER])),
    service: ReceiptService = Depends(_get_receipt_service),
):
    data = await service.generate_receipt(ride_id, user.id)
    return StandardResponse(data=ReceiptResponse(**data))
