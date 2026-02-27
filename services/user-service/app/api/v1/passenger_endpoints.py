from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.passenger import Passenger
from app.repositories.passenger_repo import PassengerRepository
from app.schemas.user import PassengerCreate, PassengerResponse, PassengerUpdate
from mediride_common.auth.dependencies import get_current_user
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import AuthorizationError, NotFoundError
from mediride_common.schemas.responses import StandardResponse

router = APIRouter(prefix="/me/passengers")


@router.get("", response_model=StandardResponse[list[PassengerResponse]])
async def list_passengers(
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = PassengerRepository(session)
    passengers = await repo.list_by_user(user.id)
    return StandardResponse(
        data=[PassengerResponse.model_validate(p) for p in passengers]
    )


@router.post("", response_model=StandardResponse[PassengerResponse])
async def create_passenger(
    request: PassengerCreate,
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = PassengerRepository(session)
    passenger = Passenger(
        user_id=user.id,
        **request.model_dump(),
    )
    await repo.create(passenger)
    return StandardResponse(
        data=PassengerResponse.model_validate(passenger),
        message="Passenger added",
    )


@router.put("/{passenger_id}", response_model=StandardResponse[PassengerResponse])
async def update_passenger(
    passenger_id: UUID,
    request: PassengerUpdate,
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = PassengerRepository(session)
    passenger = await repo.get_by_id(passenger_id)
    if not passenger or passenger.user_id != user.id:
        raise NotFoundError("Passenger not found")

    update_data = request.model_dump(exclude_unset=True)
    await repo.update(passenger_id, **update_data)

    updated = await repo.get_by_id(passenger_id)
    return StandardResponse(
        data=PassengerResponse.model_validate(updated),
        message="Passenger updated",
    )


@router.delete("/{passenger_id}", response_model=StandardResponse)
async def delete_passenger(
    passenger_id: UUID,
    user: UserClaims = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    repo = PassengerRepository(session)
    passenger = await repo.get_by_id(passenger_id)
    if not passenger or passenger.user_id != user.id:
        raise NotFoundError("Passenger not found")
    await repo.delete(passenger_id)
    return StandardResponse(message="Passenger deleted")
