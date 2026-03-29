from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.ride_package import (
    PackageKPIs,
    RidePackageCreate,
    RidePackageListResponse,
    RidePackageResponse,
    RidePackageUpdate,
)
from app.services.ride_package_service import RidePackageService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> RidePackageService:
    return RidePackageService(session)


@router.get("/packages/kpis", response_model=StandardResponse[PackageKPIs])
async def get_package_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RidePackageService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=PackageKPIs(**data))


@router.get("/packages", response_model=StandardResponse[RidePackageListResponse])
async def list_packages(
    package_type: str | None = Query(default=None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RidePackageService = Depends(_get_service),
):
    packages = await service.get_all(package_type=package_type)
    return StandardResponse(data=RidePackageListResponse(packages=packages))


@router.post("/packages", response_model=StandardResponse[RidePackageResponse])
async def create_package(
    body: RidePackageCreate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RidePackageService = Depends(_get_service),
):
    data = await service.create(
        body.model_dump(exclude_unset=True),
        admin_id=user.id,
        admin_name=user.email or "Admin",
    )
    return StandardResponse(data=RidePackageResponse(**data))


@router.get("/packages/{package_id}", response_model=StandardResponse[RidePackageResponse])
async def get_package(
    package_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RidePackageService = Depends(_get_service),
):
    data = await service.get_by_id(package_id)
    if not data:
        raise HTTPException(status_code=404, detail="Package not found")
    return StandardResponse(data=RidePackageResponse(**data))


@router.put("/packages/{package_id}", response_model=StandardResponse[RidePackageResponse])
async def update_package(
    package_id: UUID,
    body: RidePackageUpdate,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RidePackageService = Depends(_get_service),
):
    data = await service.update(
        package_id,
        body.model_dump(exclude_unset=True),
        admin_id=user.id,
        admin_name=user.email or "Admin",
    )
    if not data:
        raise HTTPException(status_code=404, detail="Package not found")
    return StandardResponse(data=RidePackageResponse(**data))


@router.put("/packages/{package_id}/toggle", response_model=StandardResponse[RidePackageResponse])
async def toggle_package(
    package_id: UUID,
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: RidePackageService = Depends(_get_service),
):
    data = await service.toggle(
        package_id, admin_id=user.id, admin_name=user.email or "Admin"
    )
    if not data:
        raise HTTPException(status_code=404, detail="Package not found")
    return StandardResponse(data=RidePackageResponse(**data))
