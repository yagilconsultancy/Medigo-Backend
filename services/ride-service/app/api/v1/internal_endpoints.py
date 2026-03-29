"""Internal API endpoints for inter-service communication."""
import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func, select

from app.dependencies import get_db
from app.models.ride_rating import RideRating
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


@router.get("/rides/active")
async def get_active_rides_internal(
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Get all active transit rides. Called by tracking-service for admin dashboard."""
    repo = RideRepository(session)
    rides = await repo.get_active_transit_rides()
    return {
        "rides": [
            {
                "id": str(r.id),
                "rider_id": str(r.rider_id),
                "driver_id": str(r.driver_id) if r.driver_id else None,
                "status": r.status,
                "ride_type": r.ride_type,
                "trip_type": r.trip_type,
                "pickup_address": r.pickup_address,
                "destination_address": r.destination_address,
                "pickup_latitude": float(r.pickup_latitude) if r.pickup_latitude else None,
                "pickup_longitude": float(r.pickup_longitude) if r.pickup_longitude else None,
                "destination_latitude": float(r.destination_latitude) if r.destination_latitude else None,
                "destination_longitude": float(r.destination_longitude) if r.destination_longitude else None,
                "estimated_distance_miles": float(r.estimated_distance_miles) if r.estimated_distance_miles else None,
                "estimated_duration_minutes": r.estimated_duration_minutes,
                "special_instructions": r.special_instructions,
                "mobility_level": r.mobility_level,
                "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
                "pickup_at": r.pickup_at.isoformat() if r.pickup_at else None,
            }
            for r in rides
        ]
    }


@router.get("/rides/completed-today-count")
async def get_completed_today_count_internal(
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Get count of rides completed today. Called by tracking-service for KPI."""
    repo = RideRepository(session)
    count = await repo.get_completed_today_count()
    return {"count": count}


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


@router.get("/drivers/{driver_id}/stats")
async def get_driver_stats_internal(
    driver_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Get driver trip stats. Called by user-service for admin driver detail."""
    repo = RideRepository(session)
    stats = await repo.get_driver_stats(driver_id)
    return stats


@router.get("/drivers/{driver_id}/ratings")
async def get_driver_ratings_internal(
    driver_id: UUID,
    limit: int = 10,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Get driver ratings. Called by user-service for admin driver detail."""
    # Get individual ratings
    result = await session.execute(
        select(RideRating)
        .where(
            RideRating.rated_user_id == driver_id,
            RideRating.rating_type == "rider_to_driver",
        )
        .order_by(RideRating.created_at.desc())
        .limit(limit)
    )
    ratings = list(result.scalars().all())

    # Get aggregate
    agg_result = await session.execute(
        select(
            func.avg(RideRating.rating),
            func.count(RideRating.id),
        ).where(
            RideRating.rated_user_id == driver_id,
            RideRating.rating_type == "rider_to_driver",
        )
    )
    row = agg_result.one()
    avg_rating = float(row[0]) if row[0] else 0.0
    total_ratings = row[1]

    return {
        "ratings": [
            {
                "ride_id": str(r.ride_id),
                "rated_by_user_id": str(r.rated_by_user_id),
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in ratings
        ],
        "average_rating": round(avg_rating, 2),
        "total_ratings": total_ratings,
    }


# ---- Rider Endpoints (for admin rider management) ----


@router.get("/riders/{rider_id}/stats")
async def get_rider_stats_internal(
    rider_id: UUID,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Get rider trip stats. Called by user-service for admin rider detail."""
    repo = RideRepository(session)
    stats = await repo.get_rider_stats(rider_id)
    return stats


@router.get("/riders/{rider_id}/rides")
async def get_rider_rides_internal(
    rider_id: UUID,
    page: int = 1,
    limit: int = 20,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Get rider completed ride history. Called by user-service for admin rider detail."""
    repo = RideRepository(session)
    offset = (page - 1) * limit
    rides, total = await repo.get_rider_completed_rides(rider_id, offset, limit)
    return {
        "rides": [
            {
                "ride_id": str(r.id),
                "date": r.dropoff_at.isoformat() if r.dropoff_at else None,
                "pickup": r.pickup_address,
                "destination": r.destination_address,
                "status": r.status,
                "fare": float(r.final_fare) if r.final_fare else None,
            }
            for r in rides
        ],
        "total": total,
    }


class BatchRiderActivityRequest(BaseModel):
    rider_ids: List[UUID]


@router.post("/riders/batch-activity")
async def get_batch_rider_activity_internal(
    body: BatchRiderActivityRequest,
    _service: str = Depends(_require_internal_service),
    session: AsyncSession = Depends(get_db),
):
    """Batch rider activity metrics. Called by user-service for admin rider activity page."""
    repo = RideRepository(session)
    result = await repo.get_batch_rider_activity(body.rider_ids)
    return result
