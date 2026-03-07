from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.saved_location_repo import SavedLocationRepository
from app.schemas.saved_location import (
    CreateSavedLocationRequest,
    ReorderLocationsRequest,
    SavedLocationResponse,
    UpdateSavedLocationRequest,
)
from app.services.saved_location_service import SavedLocationService
from mediride_common.auth.dependencies import get_current_user
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.responses import StandardResponse

router = APIRouter(prefix="/me/saved-locations")


def _get_service(session: AsyncSession = Depends(get_db)) -> SavedLocationService:
    return SavedLocationService(SavedLocationRepository(session))


@router.get("", response_model=StandardResponse[list[SavedLocationResponse]])
async def list_saved_locations(
    user: UserClaims = Depends(get_current_user),
    service: SavedLocationService = Depends(_get_service),
):
    locations = await service.list_locations(user.id)
    return StandardResponse(
        data=[SavedLocationResponse.model_validate(loc) for loc in locations]
    )


@router.post(
    "", response_model=StandardResponse[SavedLocationResponse], status_code=201
)
async def create_saved_location(
    body: CreateSavedLocationRequest,
    user: UserClaims = Depends(get_current_user),
    service: SavedLocationService = Depends(_get_service),
):
    data = body.model_dump()
    location = await service.create_location(user_id=user.id, **data)
    return StandardResponse(
        data=SavedLocationResponse.model_validate(location),
        message="Saved location created",
    )


@router.get("/{location_id}", response_model=StandardResponse[SavedLocationResponse])
async def get_saved_location(
    location_id: UUID,
    user: UserClaims = Depends(get_current_user),
    service: SavedLocationService = Depends(_get_service),
):
    location = await service.get_location(location_id, user.id)
    return StandardResponse(data=SavedLocationResponse.model_validate(location))


@router.put("/{location_id}", response_model=StandardResponse[SavedLocationResponse])
async def update_saved_location(
    location_id: UUID,
    body: UpdateSavedLocationRequest,
    user: UserClaims = Depends(get_current_user),
    service: SavedLocationService = Depends(_get_service),
):
    update_data = body.model_dump(exclude_unset=True)
    location = await service.update_location(location_id, user.id, **update_data)
    return StandardResponse(
        data=SavedLocationResponse.model_validate(location),
        message="Saved location updated",
    )


@router.delete("/{location_id}", response_model=StandardResponse)
async def delete_saved_location(
    location_id: UUID,
    user: UserClaims = Depends(get_current_user),
    service: SavedLocationService = Depends(_get_service),
):
    await service.delete_location(location_id, user.id)
    return StandardResponse(message="Saved location deleted")


@router.put("/reorder", response_model=StandardResponse[list[SavedLocationResponse]])
async def reorder_saved_locations(
    body: ReorderLocationsRequest,
    user: UserClaims = Depends(get_current_user),
    service: SavedLocationService = Depends(_get_service),
):
    locations = await service.reorder_locations(user.id, body.location_ids)
    return StandardResponse(
        data=[SavedLocationResponse.model_validate(loc) for loc in locations],
        message="Locations reordered",
    )
