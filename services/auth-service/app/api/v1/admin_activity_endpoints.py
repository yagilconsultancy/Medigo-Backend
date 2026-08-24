import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.activity_log import (
    ActivityLogItem,
    ActivityLogKPIs,
    ActivityLogListResponse,
)
from app.services.activity_log_service import ActivityLogService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> ActivityLogService:
    return ActivityLogService(session)


@router.get("/activity-logs/kpis", response_model=StandardResponse[ActivityLogKPIs])
async def get_activity_log_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: ActivityLogService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=ActivityLogKPIs(**data))


@router.get("/activity-logs", response_model=StandardResponse[ActivityLogListResponse])
async def list_activity_logs(
    severity: str | None = Query(None, description="all|info|warning|critical"),
    category: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: ActivityLogService = Depends(_get_service),
):
    severity_filter = severity if severity and severity != "all" else None
    result = await service.list_logs(
        severity=severity_filter, category=category, search=search, page=page, page_size=page_size
    )
    return StandardResponse(data=ActivityLogListResponse(**result))


@router.get("/activity-logs/export")
async def export_activity_logs(
    severity: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: ActivityLogService = Depends(_get_service),
) -> StreamingResponse:
    """Export activity logs as CSV.

    The client requests this as a blob and saves it with a .csv extension, so
    it must be real CSV -- it previously returned the ordinary JSON list
    response, giving users a JSON file named .csv.
    """
    severity_filter = severity if severity and severity != "all" else None
    result = await service.list_logs(
        severity=severity_filter, category=category, search=search, page=1, page_size=10000
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Action", "Description", "Category", "Severity", "Admin", "Timestamp",
    ])
    for item in result["items"]:
        writer.writerow([
            item["action_title"],
            item["action_description"],
            item["category"],
            item["severity"],
            item["admin_name"],
            item["created_at"].isoformat() if item["created_at"] else "",
        ])
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="activity-logs.csv"'
        },
    )
