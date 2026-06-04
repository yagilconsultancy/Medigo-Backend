from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_publisher, get_s3_client
from app.repositories.driver_repo import DriverRepository
from app.repositories.user_repo import UserRepository
from app.schemas.driver import (
    DriverProfileResponse,
    UpdateVehicleRequest,
    VehicleDetailsResponse,
)
from app.schemas.user import UserProfileResponse
from app.services.driver_service import DriverService
from app.services.user_service import UserService
from mediride_common.auth.dependencies import get_current_user, require_role
from mediride_common.auth.models import UserClaims
from mediride_common.events.publisher import EventPublisher
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse
from mediride_common.storage.s3_client import S3StorageClient

router = APIRouter()


def _get_driver_service(
    session: AsyncSession = Depends(get_db),
    publisher: EventPublisher = Depends(get_publisher),
) -> DriverService:
    return DriverService(DriverRepository(session), publisher)


@router.get("/drivers/me/vehicle", response_model=StandardResponse[VehicleDetailsResponse])
async def get_vehicle_details(
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: DriverService = Depends(_get_driver_service),
):
    driver = await service.get_driver_profile(user.id)
    return StandardResponse(data=VehicleDetailsResponse(
        vehicle_type=driver.vehicle_type,
        vehicle_make=driver.vehicle_make,
        vehicle_model=driver.vehicle_model,
        vehicle_year=driver.vehicle_year,
        vehicle_plate=driver.vehicle_plate,
        vehicle_color=driver.vehicle_color,
        vehicle_vin=driver.vehicle_vin,
        vehicle_photo_url=driver.vehicle_photo_url,
        vehicle_verified=driver.vehicle_verified,
    ))


@router.put("/drivers/me/vehicle", response_model=StandardResponse[VehicleDetailsResponse])
async def update_vehicle_details(
    body: UpdateVehicleRequest,
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: DriverService = Depends(_get_driver_service),
):
    update_data = body.model_dump(exclude_unset=True)
    driver = await service.update_driver_profile(user.id, **update_data)
    return StandardResponse(
        data=VehicleDetailsResponse(
            vehicle_type=driver.vehicle_type,
            vehicle_make=driver.vehicle_make,
            vehicle_model=driver.vehicle_model,
            vehicle_year=driver.vehicle_year,
            vehicle_plate=driver.vehicle_plate,
            vehicle_color=driver.vehicle_color,
            vehicle_vin=driver.vehicle_vin,
            vehicle_photo_url=driver.vehicle_photo_url,
            vehicle_verified=driver.vehicle_verified,
        ),
        message="Vehicle details updated",
    )


@router.put("/drivers/me/vehicle/photo", response_model=StandardResponse[VehicleDetailsResponse])
async def upload_vehicle_photo(
    file: UploadFile = File(...),
    user: UserClaims = Depends(require_role([UserRole.DRIVER])),
    service: DriverService = Depends(_get_driver_service),
    s3_client: S3StorageClient = Depends(get_s3_client),
):
    file_data = await file.read()
    file_key = f"vehicles/{user.id}/{file.filename or 'photo.jpg'}"
    await s3_client.upload_file(
        bucket=settings.S3_BUCKET_DOCUMENTS,
        key=file_key,
        file_data=file_data,
        content_type=file.content_type or "image/jpeg",
    )
    url = await s3_client.generate_presigned_url(
        bucket=settings.S3_BUCKET_DOCUMENTS,
        key=file_key,
    )
    photo_url = f"s3://{settings.S3_BUCKET_DOCUMENTS}/{file_key}"
    driver = await service.update_driver_profile(user.id, vehicle_photo_url=photo_url)
    return StandardResponse(
        data=VehicleDetailsResponse(
            vehicle_type=driver.vehicle_type,
            vehicle_make=driver.vehicle_make,
            vehicle_model=driver.vehicle_model,
            vehicle_year=driver.vehicle_year,
            vehicle_plate=driver.vehicle_plate,
            vehicle_color=driver.vehicle_color,
            vehicle_vin=driver.vehicle_vin,
            vehicle_photo_url=url,
            vehicle_verified=driver.vehicle_verified,
        ),
        message="Vehicle photo uploaded",
    )


@router.put("/me/avatar", response_model=StandardResponse[UserProfileResponse])
async def upload_avatar(
    file: UploadFile = File(...),
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    s3_client: S3StorageClient = Depends(get_s3_client),
):
    file_data = await file.read()
    file_key = f"avatars/{user.id}/{file.filename or 'avatar.jpg'}"
    await s3_client.upload_file(
        bucket=settings.S3_BUCKET_DOCUMENTS,
        key=file_key,
        file_data=file_data,
        content_type=file.content_type or "image/jpeg",
    )
    url = await s3_client.generate_presigned_url(
        bucket=settings.S3_BUCKET_DOCUMENTS,
        key=file_key,
    )
    avatar_url = f"s3://{settings.S3_BUCKET_DOCUMENTS}/{file_key}"
    user_service = UserService(UserRepository(session))
    updated_user = await user_service.update_profile(user.id, avatar_url=avatar_url)
    return StandardResponse(
        data=UserProfileResponse.model_validate(updated_user),
        message="Avatar uploaded",
    )
