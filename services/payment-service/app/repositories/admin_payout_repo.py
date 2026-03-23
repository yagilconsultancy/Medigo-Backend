from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.driver_earnings import DriverEarnings
from app.models.earnings_period import EarningsPeriod
from app.models.fare_breakdown import FareBreakdown
from app.models.transaction import Transaction
from app.models.withdrawal import Withdrawal


class AdminPayoutRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_payout_kpis(self, driver_ids: list | None = None) -> dict:
        conditions = []
        if driver_ids is not None:
            conditions.append(DriverEarnings.driver_id.in_(driver_ids))

        # Total earnings & active drivers
        earnings_result = await self.session.execute(
            select(
                func.coalesce(func.sum(DriverEarnings.total_earned), 0).label("total_earnings"),
                func.count().label("active_drivers"),
            ).where(*conditions) if conditions else select(
                func.coalesce(func.sum(DriverEarnings.total_earned), 0).label("total_earnings"),
                func.count().label("active_drivers"),
            )
        )
        e_row = earnings_result.one()

        # Pending withdrawals
        w_conditions = [Withdrawal.status.in_(["pending", "processing"])]
        if driver_ids is not None:
            w_conditions.append(Withdrawal.driver_id.in_(driver_ids))

        pending_result = await self.session.execute(
            select(
                func.count().label("pending_count"),
                func.coalesce(func.sum(Withdrawal.net_amount), 0).label("pending_total"),
            ).where(*w_conditions)
        )
        p_row = pending_result.one()

        # Completed withdrawals
        c_conditions = [Withdrawal.status == "completed"]
        if driver_ids is not None:
            c_conditions.append(Withdrawal.driver_id.in_(driver_ids))

        completed_result = await self.session.execute(
            select(
                func.coalesce(func.sum(Withdrawal.net_amount), 0).label("completed_total"),
            ).where(*c_conditions)
        )
        c_row = completed_result.one()

        return {
            "total_earnings": float(e_row.total_earnings),
            "active_drivers": e_row.active_drivers,
            "payouts_pending_count": p_row.pending_count,
            "payouts_pending_total": float(p_row.pending_total),
            "payouts_completed_total": float(c_row.completed_total),
        }

    async def get_earnings_breakdown_aggregate(self, driver_ids: list | None = None) -> dict:
        conditions = []
        if driver_ids is not None:
            conditions.append(FareBreakdown.driver_id.in_(driver_ids))

        result = await self.session.execute(
            select(
                func.coalesce(func.sum(FareBreakdown.total_fare), 0).label("gross"),
                func.coalesce(func.sum(FareBreakdown.platform_fee), 0).label("commission"),
                func.coalesce(func.sum(FareBreakdown.driver_earnings), 0).label("driver_payouts"),
            ).where(*conditions) if conditions else select(
                func.coalesce(func.sum(FareBreakdown.total_fare), 0).label("gross"),
                func.coalesce(func.sum(FareBreakdown.platform_fee), 0).label("commission"),
                func.coalesce(func.sum(FareBreakdown.driver_earnings), 0).label("driver_payouts"),
            )
        )
        row = result.one()
        return {
            "gross_ride_revenue": float(row.gross),
            "platform_commission": float(row.commission),
            "driver_payouts": float(row.driver_payouts),
        }

    async def get_monthly_earnings_distribution(self, year: int) -> list[dict]:
        result = await self.session.execute(
            select(
                extract("month", FareBreakdown.created_at).cast(Integer).label("month"),
                func.sum(FareBreakdown.driver_earnings).label("earnings"),
            )
            .where(extract("year", FareBreakdown.created_at) == year)
            .group_by(extract("month", FareBreakdown.created_at))
            .order_by(extract("month", FareBreakdown.created_at))
        )
        months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return [
            {"month": months[int(r.month)], "earnings": float(r.earnings)}
            for r in result.all()
        ]

    async def get_driver_earnings_list(
        self,
        driver_ids: list | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        conditions = [DriverEarnings.total_earned > 0]
        if driver_ids is not None:
            conditions.append(DriverEarnings.driver_id.in_(driver_ids))

        base_query = select(DriverEarnings).where(*conditions)

        count_result = await self.session.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            base_query.offset(offset).limit(limit).order_by(DriverEarnings.total_earned.desc())
        )
        rows = result.scalars().all()

        items = []
        for de in rows:
            # Get trip count from fare breakdowns
            trip_result = await self.session.execute(
                select(func.count()).where(FareBreakdown.driver_id == de.driver_id)
            )
            trips = trip_result.scalar_one()

            # Get pending withdrawal
            pending_result = await self.session.execute(
                select(func.coalesce(func.sum(Withdrawal.net_amount), 0)).where(
                    Withdrawal.driver_id == de.driver_id,
                    Withdrawal.status.in_(["pending", "processing"]),
                )
            )
            pending = float(pending_result.scalar_one())

            gross = float(de.total_earned)
            commission = round(gross * 0.20, 2)
            net = round(gross - commission, 2)

            status = "active"
            if pending > 0:
                status = "pending"

            items.append({
                "driver_id": de.driver_id,
                "trips": trips,
                "gross_earned": gross,
                "commission_percent": 20.0,
                "net_payout": net,
                "pending": pending,
                "status": status,
            })

        return items, total

    async def get_payout_schedule(self, limit: int = 10) -> list[dict]:
        result = await self.session.execute(
            select(Withdrawal)
            .order_by(Withdrawal.created_at.desc())
            .limit(limit)
        )
        withdrawals = result.scalars().all()

        items = []
        for w in withdrawals:
            items.append({
                "date": str(w.created_at.date()) if w.created_at else "",
                "amount": float(w.net_amount),
                "status": w.status,
                "driver_id": str(w.driver_id),
            })
        return items

    async def get_payouts_by_specialty(self, specialty_driver_map: dict[str, list]) -> list[dict]:
        """Get total payouts per specialty. specialty_driver_map = {specialty: [driver_ids]}."""
        results = []
        display_names = {
            "psw": "Personal Support Worker",
            "rpn": "Registered Practical Nurse",
            "rn": "Registered Nurse",
            "hca": "Health Care Aide",
            "paramedic": "Paramedic",
            "other": "Other",
        }
        for specialty, driver_ids in specialty_driver_map.items():
            if not driver_ids:
                continue
            result = await self.session.execute(
                select(
                    func.coalesce(func.sum(FareBreakdown.driver_earnings), 0).label("amount"),
                    func.count().label("count"),
                ).where(FareBreakdown.driver_id.in_(driver_ids))
            )
            row = result.one()
            results.append({
                "specialty": specialty,
                "display_name": display_names.get(specialty, specialty.upper()),
                "amount": float(row.amount),
                "count": row.count,
            })
        results.sort(key=lambda x: x["amount"], reverse=True)
        return results
