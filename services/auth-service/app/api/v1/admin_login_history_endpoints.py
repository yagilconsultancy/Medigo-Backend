import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.schemas.login_history import (
    LoginHistoryKPIs,
    LoginHistoryListResponse,
)
from app.services.login_history_service import LoginHistoryService
from mediride_common.auth.dependencies import require_role
from mediride_common.auth.models import UserClaims
from mediride_common.schemas.enums import UserRole
from mediride_common.schemas.responses import StandardResponse

router = APIRouter()


def _get_service(session: AsyncSession = Depends(get_db)) -> LoginHistoryService:
    return LoginHistoryService(session)


@router.get("/login-history/kpis", response_model=StandardResponse[LoginHistoryKPIs])
async def get_login_history_kpis(
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: LoginHistoryService = Depends(_get_service),
):
    data = await service.get_kpis()
    return StandardResponse(data=LoginHistoryKPIs(**data))


@router.get("/login-history", response_model=StandardResponse[LoginHistoryListResponse])
async def list_login_history(
    status: str | None = Query(None, description="all|success|failed"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: LoginHistoryService = Depends(_get_service),
):
    success_filter = None
    if status == "success":
        success_filter = True
    elif status == "failed":
        success_filter = False

    result = await service.list_records(
        success=success_filter, search=search, page=page, page_size=page_size
    )
    return StandardResponse(data=LoginHistoryListResponse(**result))


@router.get("/login-history/export")
async def export_login_history(
    status: str | None = Query(None),
    search: str | None = Query(None),
    user: UserClaims = Depends(require_role([UserRole.ADMIN])),
    service: LoginHistoryService = Depends(_get_service),
) -> StreamingResponse:
    """Export login history as CSV.

    The client requests this as a blob and saves it with a .csv extension, so
    it must be real CSV -- it previously returned the ordinary JSON list
    response, giving users a JSON file named .csv.
    """
    success_filter = None
    if status == "success":
        success_filter = True
    elif status == "failed":
        success_filter = False

    result = await service.list_records(
        success=success_filter, search=search, page=1, page_size=10000
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "Admin", "Email", "IP Address", "Device", "Location",
        "Status", "Failure Reason", "Suspicious", "Timestamp",
    ])
    for item in result["items"]:
        writer.writerow([
            item["admin_name"],
            item["admin_email"],
            item["ip_address"] or "",
            item["device_info"] or "",
            item["location"] or "",
            "Success" if item["success"] else "Failed",
            item["failure_reason"] or "",
            "Yes" if item["is_suspicious"] else "No",
            item["created_at"].isoformat() if item["created_at"] else "",
        ])
    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="login-history.csv"'
        },
    )
