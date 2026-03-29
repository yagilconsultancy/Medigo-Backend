import logging
from uuid import UUID

from app.clients.payment_service_client import PaymentServiceClient
from app.repositories.fleet_repo import FleetRepository
from app.schemas.fleet_earnings import (
    FleetEarningsBreakdownRow,
    FleetEarningsKPIs,
    FleetRevenueTrendPoint,
    FleetRevenueTrendResponse,
)

logger = logging.getLogger(__name__)


class FleetEarningsService:
    def __init__(
        self,
        payment_client: PaymentServiceClient,
        fleet_repo: FleetRepository,
    ):
        self.payment_client = payment_client
        self.fleet_repo = fleet_repo

    async def get_earnings_kpis(
        self, fleet_id: UUID | None = None, days: int = 30
    ) -> FleetEarningsKPIs:
        # Current period
        current = await self.payment_client.get_fleet_revenue(fleet_id, days)
        # Previous period for trend comparison
        previous = await self.payment_client.get_fleet_revenue(fleet_id, days * 2)

        current_revenue = float(current.get("total_revenue", 0)) if current else 0.0
        current_payouts = float(current.get("total_driver_earnings", 0)) if current else 0.0

        # Calculate previous period values (total - current = previous period)
        prev_total_revenue = float(previous.get("total_revenue", 0)) if previous else 0.0
        prev_total_payouts = float(previous.get("total_driver_earnings", 0)) if previous else 0.0
        prev_revenue = prev_total_revenue - current_revenue
        prev_payouts = prev_total_payouts - current_payouts

        # Calculate change percentages
        revenue_change = _calc_change_percent(current_revenue, prev_revenue)
        payout_change = _calc_change_percent(current_payouts, prev_payouts)

        return FleetEarningsKPIs(
            total_revenue=current_revenue,
            total_payouts=current_payouts,
            revenue_change_percent=revenue_change,
            payout_change_percent=payout_change,
            revenue_trend=_trend_direction(revenue_change),
            payout_trend=_trend_direction(payout_change),
        )

    async def get_revenue_trend(
        self, fleet_id: UUID | None = None, days: int = 30
    ) -> FleetRevenueTrendResponse:
        trend_data = await self.payment_client.get_fleet_revenue_trend(fleet_id, days)
        return FleetRevenueTrendResponse(
            period_days=days,
            trend=[
                FleetRevenueTrendPoint(date=t["date"], revenue=float(t["revenue"]))
                for t in trend_data
            ],
        )

    async def get_earnings_breakdown(
        self,
        fleet_id: UUID | None = None,
        days: int = 30,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[FleetEarningsBreakdownRow], int]:
        # Get all fleets from local DB
        fleets, total = await self.fleet_repo.list_all(offset=0, limit=1000)

        if fleet_id:
            fleets = [f for f in fleets if f.id == fleet_id]
            total = len(fleets)

        # Build fleet_id -> name map
        fleet_map = {f.id: f.name for f in fleets}
        fleet_ids = list(fleet_map.keys())

        if not fleet_ids:
            return [], 0

        # Batch query payment-service
        breakdowns = await self.payment_client.get_fleet_earnings_breakdown(
            fleet_ids, days
        )

        # Build response rows
        rows = []
        for fid, name in fleet_map.items():
            fid_str = str(fid)
            data = breakdowns.get(fid_str, {})
            rows.append(
                FleetEarningsBreakdownRow(
                    fleet_id=fid,
                    fleet_name=name,
                    trips=data.get("trips", 0),
                    revenue=data.get("revenue", 0.0),
                    commission=data.get("commission", 0.0),
                    net_earnings=data.get("net_earnings", 0.0),
                    avg_per_trip=data.get("avg_per_trip", 0.0),
                )
            )

        # Sort by revenue descending
        rows.sort(key=lambda r: r.revenue, reverse=True)

        # Paginate
        paginated = rows[offset : offset + limit]
        return paginated, len(rows)


def _calc_change_percent(current: float, previous: float) -> float:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


def _trend_direction(change_percent: float) -> str:
    if change_percent > 0:
        return "up"
    elif change_percent < 0:
        return "down"
    return "flat"
