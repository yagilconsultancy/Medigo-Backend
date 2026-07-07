import uuid
from datetime import date
from uuid import UUID

from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver_document import DriverDocument
from app.models.driver_profile import DriverProfile
from app.models.driver_suspension_log import DriverSuspensionLog
from app.models.fleet import Fleet
from app.models.user import User
from app.models.vehicle import Vehicle


class AdminDriverRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_driver_kpis(self, fleet_id: UUID | None = None) -> dict:
        base = select(DriverProfile).where(User.role == "driver").join(User, User.id == DriverProfile.user_id)
        if fleet_id:
            base = base.where(DriverProfile.business_id == fleet_id)

        # Total
        total_result = await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = total_result.scalar_one()

        # By account_status
        status_query = (
            select(DriverProfile.account_status, func.count())
            .join(User, User.id == DriverProfile.user_id)
            .where(User.role == "driver")
        )
        if fleet_id:
            status_query = status_query.where(DriverProfile.business_id == fleet_id)
        status_query = status_query.group_by(DriverProfile.account_status)

        result = await self.session.execute(status_query)
        status_counts = {row[0]: row[1] for row in result.all()}

        # Online count
        online_query = (
            select(func.count())
            .select_from(DriverProfile)
            .join(User, User.id == DriverProfile.user_id)
            .where(User.role == "driver", DriverProfile.is_online.is_(True))
        )
        if fleet_id:
            online_query = online_query.where(DriverProfile.business_id == fleet_id)
        online_result = await self.session.execute(online_query)
        online_count = online_result.scalar_one()

        active = status_counts.get("active", 0)
        approval_rate = round((active / total * 100), 1) if total > 0 else 0.0

        return {
            "total_drivers": total,
            "active_count": active,
            "suspended_count": status_counts.get("suspended", 0),
            "pending_count": status_counts.get("pending", 0),
            "online_count": online_count,
            "approval_rate": approval_rate,
        }

    async def count_online_drivers_in_set(self, driver_ids: set[str]) -> int:
        """Count how many online drivers are in the given set of driver IDs."""
        uuid_ids = [uuid.UUID(did) for did in driver_ids]
        result = await self.session.execute(
            select(func.count())
            .select_from(DriverProfile)
            .join(User, User.id == DriverProfile.user_id)
            .where(
                User.role == "driver",
                DriverProfile.is_online.is_(True),
                DriverProfile.user_id.in_(uuid_ids),
            )
        )
        return result.scalar_one()

    async def list_drivers_for_admin(
        self,
        search: str | None = None,
        fleet_id: UUID | None = None,
        account_status: str | None = None,
        is_online: bool | None = None,
        sort_by: str = "created_at",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        query = (
            select(User, DriverProfile, Fleet.name.label("fleet_name"), Vehicle)
            .join(DriverProfile, DriverProfile.user_id == User.id)
            .outerjoin(Fleet, Fleet.id == DriverProfile.business_id)
            .outerjoin(Vehicle, Vehicle.driver_profile_id == DriverProfile.user_id)
            .where(User.role == "driver")
        )

        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    User.first_name.ilike(search_term),
                    User.last_name.ilike(search_term),
                    User.email.ilike(search_term),
                    User.phone.ilike(search_term),
                )
            )

        if fleet_id:
            query = query.where(DriverProfile.business_id == fleet_id)
        if account_status:
            query = query.where(DriverProfile.account_status == account_status)
        if is_online is not None:
            query = query.where(DriverProfile.is_online == is_online)

        # Count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # Sort
        sort_col = {
            "created_at": DriverProfile.created_at.desc(),
            "name": User.first_name.asc(),
            "rating": DriverProfile.rating.desc(),
            "total_trips": DriverProfile.total_trips.desc(),
        }.get(sort_by, DriverProfile.created_at.desc())

        query = query.order_by(sort_col).offset(offset).limit(limit)
        result = await self.session.execute(query)
        rows = result.all()

        drivers = []
        for user, driver, fleet_name, vehicle in rows:
            # Prefer assigned Vehicle fields, fall back to DriverProfile fields
            drivers.append({
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": user.phone,
                "avatar_url": user.avatar_url,
                "fleet_id": driver.business_id,
                "fleet_name": fleet_name,
                "account_status": driver.account_status,
                "is_online": driver.is_online,
                "is_approved": driver.is_approved,
                "rating": float(driver.rating),
                "total_trips": driver.total_trips,
                "vehicle_type": vehicle.category if vehicle else driver.vehicle_type,
                "vehicle_make": vehicle.make if vehicle else driver.vehicle_make,
                "vehicle_model": vehicle.model if vehicle else driver.vehicle_model,
                "vehicle_year": vehicle.year if vehicle else driver.vehicle_year,
                "vehicle_plate": vehicle.plate_number if vehicle else driver.vehicle_plate,
                "specialty": driver.specialty,
                "created_at": driver.created_at,
            })

        return drivers, total

    async def get_driver_detail(self, driver_user_id: UUID) -> dict | None:
        result = await self.session.execute(
            select(User, DriverProfile, Fleet.name.label("fleet_name"))
            .join(DriverProfile, DriverProfile.user_id == User.id)
            .outerjoin(Fleet, Fleet.id == DriverProfile.business_id)
            .where(User.id == driver_user_id, User.role == "driver")
        )
        row = result.one_or_none()
        if not row:
            return None

        user, driver, fleet_name = row
        return {
            "user_id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": user.phone,
            "avatar_url": user.avatar_url,
            "fleet_id": driver.business_id,
            "fleet_name": fleet_name,
            "account_status": driver.account_status,
            "is_online": driver.is_online,
            "is_approved": driver.is_approved,
            "rating": float(driver.rating),
            "total_trips": driver.total_trips,
            "specialty": driver.specialty,
            "service_capabilities": driver.service_capabilities or [],
            "vehicle_type": driver.vehicle_type,
            "vehicle_make": driver.vehicle_make,
            "vehicle_model": driver.vehicle_model,
            "vehicle_year": driver.vehicle_year,
            "vehicle_plate": driver.vehicle_plate,
            "vehicle_color": driver.vehicle_color,
            "vehicle_vin": driver.vehicle_vin,
            "vehicle_photo_url": driver.vehicle_photo_url,
            "license_number": driver.license_number,
            "license_expiry": driver.license_expiry,
            "medical_transport_certification": driver.medical_transport_certification,
            "date_of_birth": driver.date_of_birth,
            "address": driver.address,
            "city": driver.city,
            "province": driver.province,
            "postal_code": driver.postal_code,
            "emergency_contact_name": driver.emergency_contact_name,
            "emergency_contact_phone": driver.emergency_contact_phone,
            "background_check_status": driver.background_check_status,
            "suspension_reason": driver.suspension_reason,
            "suspended_at": driver.suspended_at,
            "deactivated_at": driver.deactivated_at,
            "approved_at": driver.approved_at,
            "notes": driver.notes,
            "invited_via_email": driver.invited_via_email,
            "created_at": driver.created_at,
            "updated_at": driver.updated_at,
        }

    async def get_driver_documents(self, driver_user_id: UUID) -> list[dict]:
        result = await self.session.execute(
            select(DriverDocument)
            .where(DriverDocument.user_id == driver_user_id)
            .order_by(DriverDocument.created_at.desc())
        )
        docs = result.scalars().all()
        return [
            {
                "id": d.id,
                "document_type": d.document_type,
                "file_name": d.file_name,
                "verification_status": d.verification_status,
                "expires_at": d.expires_at,
                "created_at": d.created_at,
            }
            for d in docs
        ]

    def _compute_document_status(self, docs: list[dict]) -> str:
        if not docs:
            return "missing"
        statuses = [d["verification_status"] for d in docs]
        if all(s == "approved" for s in statuses):
            return "all_verified"
        if any(s == "pending" for s in statuses):
            return "pending"
        if any(s == "rejected" for s in statuses):
            return "rejected"
        return "incomplete"

    async def get_document_kpis(self) -> dict:
        # Total drivers
        total_result = await self.session.execute(
            select(func.count())
            .select_from(DriverProfile)
            .join(User, User.id == DriverProfile.user_id)
            .where(User.role == "driver")
        )
        total_drivers = total_result.scalar_one()

        # Pending review documents
        pending_result = await self.session.execute(
            select(func.count(func.distinct(DriverDocument.user_id)))
            .where(DriverDocument.verification_status == "pending")
        )
        pending_review = pending_result.scalar_one()

        # Expired documents
        expired_result = await self.session.execute(
            select(func.count(func.distinct(DriverDocument.user_id)))
            .where(
                DriverDocument.expires_at.isnot(None),
                DriverDocument.expires_at < func.current_date(),
            )
        )
        expired_docs = expired_result.scalar_one()

        # Drivers with all docs verified (has at least one doc and all are approved)
        drivers_with_docs = await self.session.execute(
            select(DriverDocument.user_id)
            .group_by(DriverDocument.user_id)
            .having(
                func.count(
                    case((DriverDocument.verification_status != "approved", 1))
                ) == 0
            )
        )
        all_verified = len(drivers_with_docs.all())

        return {
            "total_drivers": total_drivers,
            "all_docs_verified": all_verified,
            "pending_review": pending_review,
            "expired_docs": expired_docs,
        }

    async def list_drivers_with_document_status(
        self,
        search: str | None = None,
        status_filter: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        query = (
            select(User, DriverProfile, Fleet.name.label("fleet_name"))
            .join(DriverProfile, DriverProfile.user_id == User.id)
            .outerjoin(Fleet, Fleet.id == DriverProfile.business_id)
            .where(User.role == "driver")
        )

        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    User.first_name.ilike(search_term),
                    User.last_name.ilike(search_term),
                    User.email.ilike(search_term),
                )
            )

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(DriverProfile.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        rows = result.all()

        drivers = []
        for user, driver, fleet_name in rows:
            docs = await self.get_driver_documents(user.id)
            doc_status = self._compute_document_status(docs)

            if status_filter and doc_status != status_filter:
                continue

            drivers.append({
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "fleet_name": fleet_name,
                "documents": docs,
                "document_status": doc_status,
            })

        return drivers, total

    async def get_status_kpis(self) -> dict:
        query = (
            select(DriverProfile.account_status, func.count())
            .join(User, User.id == DriverProfile.user_id)
            .where(User.role == "driver")
            .group_by(DriverProfile.account_status)
        )
        result = await self.session.execute(query)
        counts = {row[0]: row[1] for row in result.all()}

        return {
            "active_count": counts.get("active", 0),
            "suspended_count": counts.get("suspended", 0),
            "pending_count": counts.get("pending", 0),
            "deactivated_count": counts.get("deactivated", 0),
        }

    async def get_drivers_by_status(self, status: str) -> list[dict]:
        query = (
            select(User, DriverProfile, Fleet.name.label("fleet_name"))
            .join(DriverProfile, DriverProfile.user_id == User.id)
            .outerjoin(Fleet, Fleet.id == DriverProfile.business_id)
            .where(User.role == "driver", DriverProfile.account_status == status)
            .order_by(DriverProfile.created_at.desc())
        )
        result = await self.session.execute(query)
        rows = result.all()

        return [
            {
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "fleet_name": fleet_name,
                "account_status": driver.account_status,
                "suspension_reason": driver.suspension_reason,
                "suspended_at": driver.suspended_at,
                "created_at": driver.created_at,
            }
            for user, driver, fleet_name in rows
        ]

    async def create_suspension_log(
        self,
        driver_id: UUID,
        action: str,
        reason: str | None,
        performed_by: UUID,
    ) -> DriverSuspensionLog:
        log = DriverSuspensionLog(
            id=uuid.uuid4(),
            driver_id=driver_id,
            action=action,
            reason=reason,
            performed_by=performed_by,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def delete_driver_account(self, driver_user_id: UUID) -> None:
        await self.session.execute(
            delete(DriverSuspensionLog).where(DriverSuspensionLog.driver_id == driver_user_id)
        )
        await self.session.execute(
            delete(DriverDocument).where(DriverDocument.user_id == driver_user_id)
        )
        await self.session.execute(
            delete(Vehicle).where(Vehicle.driver_profile_id == driver_user_id)
        )
        await self.session.execute(
            delete(DriverProfile).where(DriverProfile.user_id == driver_user_id)
        )
        await self.session.execute(
            delete(User).where(User.id == driver_user_id, User.role == "driver")
        )
        await self.session.flush()

    async def get_suspension_history(self, driver_id: UUID) -> list[dict]:
        result = await self.session.execute(
            select(DriverSuspensionLog)
            .where(DriverSuspensionLog.driver_id == driver_id)
            .order_by(DriverSuspensionLog.created_at.desc())
        )
        logs = result.scalars().all()
        return [
            {
                "id": log.id,
                "action": log.action,
                "reason": log.reason,
                "performed_by": log.performed_by,
                "created_at": log.created_at,
            }
            for log in logs
        ]

    async def update_driver_profile(self, driver_user_id: UUID, **kwargs) -> None:
        from sqlalchemy import update
        await self.session.execute(
            update(DriverProfile)
            .where(DriverProfile.user_id == driver_user_id)
            .values(**kwargs)
        )

    async def update_user(self, user_id: UUID, **kwargs) -> None:
        from sqlalchemy import update
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(**kwargs)
        )

    async def create_driver_profile(self, **kwargs) -> DriverProfile:
        driver = DriverProfile(**kwargs)
        self.session.add(driver)
        await self.session.flush()
        return driver

    async def create_user(self, **kwargs) -> User:
        user = User(**kwargs)
        self.session.add(user)
        await self.session.flush()
        return user
