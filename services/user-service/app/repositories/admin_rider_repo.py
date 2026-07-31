import uuid
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rider_kyc import RiderKYC
from app.models.user import User
from app.repositories.user_repo import user_search_filter
from mediride_common.schemas.enums import KYCStatus


class AdminRiderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _compute_status(self, user: User) -> str:
        if user.suspended_at is not None:
            return "suspended"
        if not user.is_active:
            return "inactive"
        return "active"

    async def get_rider_kpis(self) -> dict:
        base = select(User).where(User.role == "rider", User.deleted_at.is_(None))

        total_result = await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = total_result.scalar_one()

        active_result = await self.session.execute(
            select(func.count()).where(
                User.role == "rider",
                User.deleted_at.is_(None),
                User.is_active.is_(True),
                User.suspended_at.is_(None),
            )
        )
        active_count = active_result.scalar_one()

        suspended_result = await self.session.execute(
            select(func.count()).where(
                User.role == "rider",
                User.deleted_at.is_(None),
                User.suspended_at.isnot(None),
            )
        )
        suspended_count = suspended_result.scalar_one()

        return {
            "total_riders": total,
            "active_count": active_count,
            "suspended_count": suspended_count,
        }

    async def list_riders_for_admin(
        self,
        search: str | None = None,
        status: str | None = None,
        kyc_status: str | None = None,
        sort_by: str = "created_at",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        query = select(User).where(User.role == "rider", User.deleted_at.is_(None))

        if search:
            query = query.where(user_search_filter(search))

        if kyc_status:
            if kyc_status == KYCStatus.NOT_STARTED:
                # Riders with no rider_kyc row have not started verification.
                query = query.where(
                    or_(
                        User.id.notin_(select(RiderKYC.user_id)),
                        User.id.in_(
                            select(RiderKYC.user_id).where(
                                RiderKYC.kyc_status == KYCStatus.NOT_STARTED
                            )
                        ),
                    )
                )
            else:
                query = query.where(
                    User.id.in_(
                        select(RiderKYC.user_id).where(
                            RiderKYC.kyc_status == kyc_status
                        )
                    )
                )

        if status == "active":
            query = query.where(User.is_active.is_(True), User.suspended_at.is_(None))
        elif status == "suspended":
            query = query.where(User.suspended_at.isnot(None))
        elif status == "inactive":
            query = query.where(User.is_active.is_(False), User.suspended_at.is_(None))

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        sort_col = {
            "created_at": User.created_at.desc(),
            "name": User.first_name.asc(),
        }.get(sort_by, User.created_at.desc())

        query = query.order_by(sort_col).offset(offset).limit(limit)
        result = await self.session.execute(query)
        users = list(result.scalars().all())

        riders = []
        for user in users:
            riders.append({
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": user.phone,
                "avatar_url": user.avatar_url,
                "joined_at": user.created_at,
                "status": self._compute_status(user),
                "kyc_status": (
                    user.kyc.kyc_status if user.kyc else KYCStatus.NOT_STARTED
                ),
            })

        return riders, total

    async def get_rider_detail(self, rider_id: UUID) -> dict | None:
        result = await self.session.execute(
            select(User).where(
                User.id == rider_id, User.role == "rider", User.deleted_at.is_(None)
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            return None

        emergency_contacts = [
            {
                "name": ec.name,
                "phone": ec.phone,
                "relationship_type": ec.relationship_type,
            }
            for ec in (user.emergency_contacts or [])
        ]

        return {
            "user_id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "date_of_birth": user.date_of_birth,
            "gender": user.gender,
            "home_address": user.home_address,
            "city": user.city,
            "province": user.province,
            "postal_code": user.postal_code,
            "country": user.country,
            "medical_notes": user.medical_notes,
            "insurance_provider": user.insurance_provider,
            "insurance_policy_number": user.insurance_policy_number,
            "insurance_group_number": user.insurance_group_number,
            "insurance_member_id": user.insurance_member_id,
            "insurance_expiry": user.insurance_expiry,
            "status": self._compute_status(user),
            "suspension_reason": user.suspension_reason,
            "suspended_at": user.suspended_at,
            "created_at": user.created_at,
            "emergency_contacts": emergency_contacts,
            # A rider with no record simply hasn't started verification.
            "kyc": user.kyc or {"kyc_status": KYCStatus.NOT_STARTED},
        }

    async def get_rider_ids(self, offset: int = 0, limit: int = 20) -> tuple[list[dict], int]:
        """Get rider basic info for activity page."""
        query = select(User).where(User.role == "rider", User.deleted_at.is_(None))

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(User.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        users = list(result.scalars().all())

        riders = []
        for user in users:
            primary_ec = next(
                (ec for ec in (user.emergency_contacts or []) if ec.is_primary),
                (user.emergency_contacts or [None])[0] if user.emergency_contacts else None,
            )
            riders.append({
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "avatar_url": user.avatar_url,
                "date_of_birth": user.date_of_birth,
                "email": user.email,
                "phone": user.phone,
                "insurance_provider": user.insurance_provider,
                "insurance_policy_number": user.insurance_policy_number,
                "emergency_contact_name": primary_ec.name if primary_ec else None,
                "emergency_contact_relationship": primary_ec.relationship_type if primary_ec else None,
                "member_since": user.created_at,
                "status": self._compute_status(user),
            })

        return riders, total

    async def suspend_rider(
        self, rider_id: UUID, reason: str, admin_id: UUID
    ) -> None:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(User)
            .where(User.id == rider_id)
            .values(
                suspended_at=now,
                suspension_reason=reason,
                suspended_by=admin_id,
            )
        )

    async def reinstate_rider(self, rider_id: UUID) -> None:
        await self.session.execute(
            update(User)
            .where(User.id == rider_id)
            .values(
                suspended_at=None,
                suspension_reason=None,
                suspended_by=None,
                is_active=True,
            )
        )

    # ==================== Rider profile & KYC ====================

    async def update_user(self, rider_id: UUID, **kwargs) -> None:
        if not kwargs:
            return
        await self.session.execute(
            update(User).where(User.id == rider_id).values(**kwargs)
        )

    async def get_kyc(self, rider_id: UUID) -> RiderKYC | None:
        result = await self.session.execute(
            select(RiderKYC).where(RiderKYC.user_id == rider_id)
        )
        return result.scalar_one_or_none()

    async def upsert_kyc(self, rider_id: UUID, **kwargs) -> RiderKYC:
        """Create the rider's KYC row on first write, then update in place."""
        record = await self.get_kyc(rider_id)
        if record is None:
            record = RiderKYC(user_id=rider_id, **kwargs)
            self.session.add(record)
            await self.session.flush()
            return record

        for key, value in kwargs.items():
            setattr(record, key, value)
        await self.session.flush()
        return record
