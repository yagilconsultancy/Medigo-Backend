from datetime import date, timedelta, timezone, datetime
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fleet import Fleet
from app.models.vehicle import Vehicle
from app.models.vehicle_document import VehicleDocument


class VehicleDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, doc: VehicleDocument) -> VehicleDocument:
        self.session.add(doc)
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def get_by_id(self, doc_id: UUID) -> VehicleDocument | None:
        result = await self.session.execute(
            select(VehicleDocument).where(VehicleDocument.id == doc_id)
        )
        return result.scalar_one_or_none()

    async def list_by_vehicle(self, vehicle_id: UUID) -> list[VehicleDocument]:
        result = await self.session.execute(
            select(VehicleDocument)
            .where(VehicleDocument.vehicle_id == vehicle_id)
            .order_by(VehicleDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_type(
        self, vehicle_id: UUID, document_type: str
    ) -> VehicleDocument | None:
        result = await self.session.execute(
            select(VehicleDocument)
            .where(
                VehicleDocument.vehicle_id == vehicle_id,
                VehicleDocument.document_type == document_type,
            )
            .order_by(VehicleDocument.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_document_kpis(self) -> dict:
        today = date.today()
        expiring_threshold = today + timedelta(days=30)

        result = await self.session.execute(
            select(
                func.count().label("total"),
                func.count().filter(
                    or_(
                        VehicleDocument.expires_at.is_(None),
                        VehicleDocument.expires_at > expiring_threshold,
                    )
                ).label("valid"),
                func.count().filter(
                    VehicleDocument.expires_at.isnot(None),
                    VehicleDocument.expires_at <= expiring_threshold,
                    VehicleDocument.expires_at > today,
                ).label("expiring_soon"),
                func.count().filter(
                    VehicleDocument.expires_at.isnot(None),
                    VehicleDocument.expires_at <= today,
                ).label("expired"),
            )
        )
        row = result.one()
        return {
            "total_documents": row.total,
            "valid_count": row.valid,
            "expiring_soon_count": row.expiring_soon,
            "expired_count": row.expired,
        }

    async def get_document_overview(
        self,
        search: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        query = (
            select(Vehicle, Fleet.name.label("fleet_name"))
            .outerjoin(Fleet, Fleet.id == Vehicle.business_id)
            .where(Vehicle.deleted_at.is_(None))
        )

        if search:
            pattern = f"%{search}%"
            query = query.where(
                or_(
                    Vehicle.make.ilike(pattern),
                    Vehicle.model.ilike(pattern),
                    Vehicle.plate_number.ilike(pattern),
                    Vehicle.vehicle_name.ilike(pattern),
                )
            )

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        query = query.order_by(Vehicle.created_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        rows = result.all()

        today = date.today()
        expiring_threshold = today + timedelta(days=30)
        doc_types = ["registration", "insurance_certificate", "safety_inspection"]

        vehicles = []
        for vehicle, fleet_name in rows:
            docs = await self.list_by_vehicle(vehicle.id)
            doc_map = {}
            for d in docs:
                if d.document_type not in doc_map:
                    doc_map[d.document_type] = d

            doc_matrix = []
            for dt in doc_types:
                doc = doc_map.get(dt)
                if doc:
                    if doc.expires_at and doc.expires_at <= today:
                        status = "expired"
                    elif doc.expires_at and doc.expires_at <= expiring_threshold:
                        status = "expiring_soon"
                    else:
                        status = "valid"
                    doc_matrix.append({
                        "document_type": dt,
                        "status": status,
                        "file_name": doc.file_name,
                        "expires_at": doc.expires_at,
                        "doc_id": doc.id,
                    })
                else:
                    doc_matrix.append({
                        "document_type": dt,
                        "status": "missing",
                        "file_name": None,
                        "expires_at": None,
                        "doc_id": None,
                    })

            vehicles.append({
                "vehicle_id": vehicle.id,
                "vehicle_name": vehicle.vehicle_name,
                "make": vehicle.make,
                "model": vehicle.model,
                "plate_number": vehicle.plate_number,
                "fleet_name": fleet_name,
                "documents": doc_matrix,
            })

        return vehicles, total
