"""Internal API endpoints for inter-service communication."""
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.ride_repo import RideRepository
from app.schemas.ride import RideResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal")


def _require_internal_service(
    x_internal_service: str | None = Header(None),
) -> str:
    if not x_internal_service:
        raise HTTPException(status_code=403, detail="Internal access only")
    return x_internal_service


class UpdateFareRequest(BaseModel):
    final_fare: float


@router.get("/rides/{ride_id}")
async def get_ride_internal(
    ride_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    repo = RideRepository(session)
    ride = await repo.get_by_id(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")

    data = RideResponse.model_validate(ride).model_dump(mode="json")

    # Enrich with fields needed by payment-service fare calculation
    data["timeline"] = [
        {
            "to_status": log.to_status,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in (ride.status_logs or [])
    ]
    data["use_highway_407"] = ride.use_highway_407
    data["highway_407_route"] = ride.highway_407_route
    data["is_dialysis_trip"] = ride.is_dialysis_trip
    data["actual_distance_miles"] = float(ride.actual_distance_miles) if ride.actual_distance_miles else None
    data["estimated_distance_miles"] = float(ride.estimated_distance_miles) if ride.estimated_distance_miles else None
    data["pickup_at"] = ride.pickup_at.isoformat() if ride.pickup_at else None
    data["pickup_address"] = ride.pickup_address
    data["destination_address"] = ride.destination_address

    return data


@router.get("/rides/driver/{driver_id}/completed")
async def get_driver_completed_rides(
    driver_id: UUID,
    page: int = 1,
    limit: int = 50,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    repo = RideRepository(session)
    offset = (page - 1) * limit
    rides, total = await repo.get_by_driver(driver_id, "completed", offset, limit)
    return {
        "rides": [RideResponse.model_validate(r).model_dump(mode="json") for r in rides],
        "total": total,
    }


@router.put("/rides/{ride_id}/fare")
async def update_ride_fare(
    ride_id: UUID,
    request: UpdateFareRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    repo = RideRepository(session)
    ride = await repo.get_by_id(ride_id)
    if not ride:
        raise HTTPException(status_code=404, detail="Ride not found")
    await repo.update(ride_id, final_fare=request.final_fare)
    return {"updated": True, "ride_id": str(ride_id), "final_fare": request.final_fare}
