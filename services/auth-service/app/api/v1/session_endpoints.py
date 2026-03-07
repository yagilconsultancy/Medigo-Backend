from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.session_repo import SessionRepository
from app.schemas.session import SessionResponse
from mediride_common.auth.dependencies import get_current_user
from mediride_common.auth.models import UserClaims
from mediride_common.exceptions import NotFoundError
from mediride_common.schemas.responses import StandardResponse

router = APIRouter(prefix="/sessions")


def _get_repo(session: AsyncSession = Depends(get_db)) -> SessionRepository:
    return SessionRepository(session)


@router.get("", response_model=StandardResponse[list[SessionResponse]])
async def list_active_sessions(
    user: UserClaims = Depends(get_current_user),
    repo: SessionRepository = Depends(_get_repo),
):
    sessions = await repo.get_active_by_user(user.id)
    return StandardResponse(
        data=[SessionResponse.model_validate(s) for s in sessions],
    )


@router.delete("/{session_id}", response_model=StandardResponse[None])
async def revoke_session(
    session_id: UUID,
    user: UserClaims = Depends(get_current_user),
    repo: SessionRepository = Depends(_get_repo),
):
    session_obj = await repo.get_by_id(session_id)
    if not session_obj or session_obj.user_id != user.id:
        raise NotFoundError("Session not found")
    await repo.deactivate(session_id)
    return StandardResponse(message="Session revoked")


@router.delete("", response_model=StandardResponse[None])
async def revoke_all_sessions(
    user: UserClaims = Depends(get_current_user),
    repo: SessionRepository = Depends(_get_repo),
):
    await repo.deactivate_all(user.id)
    return StandardResponse(message="All sessions revoked")
