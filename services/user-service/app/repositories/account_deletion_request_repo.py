from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import String, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account_deletion_request import AccountDeletionRequest


class AccountDeletionRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, request: AccountDeletionRequest
    ) -> AccountDeletionRequest:
        self.session.add(request)
        await self.session.flush()
        await self.session.refresh(request)
        return request

    async def get_by_id(self, request_id: UUID) -> AccountDeletionRequest | None:
        result = await self.session.execute(
            select(AccountDeletionRequest).where(
                AccountDeletionRequest.id == request_id
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_email(
        self, email: str
    ) -> AccountDeletionRequest | None:
        """Most recent request for this email that is still in flight.

        Re-submitting the form reuses this row rather than stacking duplicates
        in the admin queue, and it is also the row the verify/resend endpoints
        act on - they are given only an email, never a request id.
        """
        result = await self.session.execute(
            select(AccountDeletionRequest)
            .where(
                func.lower(AccountDeletionRequest.email) == email.lower(),
                AccountDeletionRequest.status.in_(
                    [
                        AccountDeletionRequest.STATUS_PENDING_VERIFICATION,
                        AccountDeletionRequest.STATUS_PENDING_REVIEW,
                    ]
                ),
            )
            .order_by(desc(AccountDeletionRequest.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        status_filter: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[AccountDeletionRequest], int]:
        conditions = []

        if status_filter:
            conditions.append(AccountDeletionRequest.status == status_filter)

        if search:
            term = f"%{search.strip().lower()}%"
            conditions.append(
                or_(
                    func.lower(AccountDeletionRequest.full_name).like(term),
                    func.lower(AccountDeletionRequest.email).like(term),
                    func.lower(func.coalesce(AccountDeletionRequest.phone, "")).like(term),
                    func.lower(AccountDeletionRequest.id.cast(String)).like(term),
                )
            )

        base_query = select(AccountDeletionRequest)
        if conditions:
            base_query = base_query.where(*conditions)

        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.order_by(desc(AccountDeletionRequest.created_at))
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, request_id: UUID, **kwargs) -> None:
        request = await self.get_by_id(request_id)
        if request:
            for key, value in kwargs.items():
                setattr(request, key, value)
            await self.session.flush()

    async def count_recent_for_email(self, email: str, since: datetime) -> int:
        """How many requests this email has filed since `since`.

        Backs the abuse guard on the public endpoint: the form is
        unauthenticated, so without this one address could be spammed with
        deletion codes.
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(AccountDeletionRequest)
            .where(
                func.lower(AccountDeletionRequest.email) == email.lower(),
                AccountDeletionRequest.created_at >= since,
            )
        )
        return result.scalar_one()

    async def get_kpis(self) -> dict:
        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.count()
                .filter(
                    AccountDeletionRequest.status
                    == AccountDeletionRequest.STATUS_PENDING_REVIEW
                )
                .label("pending_review"),
                func.count()
                .filter(
                    AccountDeletionRequest.status
                    == AccountDeletionRequest.STATUS_APPROVED
                )
                .label("approved"),
                func.count()
                .filter(
                    AccountDeletionRequest.status
                    == AccountDeletionRequest.STATUS_REJECTED
                )
                .label("rejected"),
                func.count()
                .filter(
                    AccountDeletionRequest.status
                    == AccountDeletionRequest.STATUS_PENDING_VERIFICATION
                )
                .label("awaiting_verification"),
            ).select_from(AccountDeletionRequest)
        )
        row = result.one()
        return {
            "total_requests": row.total,
            "pending_review": row.pending_review,
            "approved": row.approved,
            "rejected": row.rejected,
            "awaiting_verification": row.awaiting_verification,
        }
