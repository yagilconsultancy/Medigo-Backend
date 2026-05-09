import logging
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.config import settings
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fare_breakdown import FareBreakdown
from app.models.service_type_config import ServiceTypeConfig
from app.repositories.pricing_change_log_repo import PricingChangeLogRepository
from app.repositories.service_type_config_repo import ServiceTypeConfigRepository

logger = logging.getLogger(__name__)


class PricingDashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.config_repo = ServiceTypeConfigRepository(session)
        self.log_repo = PricingChangeLogRepository(session)

    async def get_kpis(self) -> dict:
        now = datetime.now(ZoneInfo(settings.DEFAULT_TIMEZONE))
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Monthly revenue
        rev_q = select(
            func.coalesce(func.sum(FareBreakdown.total_fare), 0)
        ).where(FareBreakdown.created_at >= month_start)
        rev_result = await self.session.execute(rev_q)
        monthly_revenue = rev_result.scalar() or Decimal("0")

        # Average trip fare
        avg_q = select(
            func.coalesce(func.avg(FareBreakdown.total_fare), 0)
        ).where(FareBreakdown.created_at >= month_start)
        avg_result = await self.session.execute(avg_q)
        avg_trip_fare = avg_result.scalar() or Decimal("0")

        # Active service types
        configs = await self.config_repo.get_all(active_only=True)
        active_service_types = len(configs)

        # Premium ride percent (WAV + stretcher rides)
        total_q = select(func.count()).select_from(FareBreakdown).where(
            FareBreakdown.created_at >= month_start
        )
        total_result = await self.session.execute(total_q)
        total_rides = total_result.scalar() or 0

        premium_percent = Decimal("0")
        if total_rides > 0:
            premium_q = select(func.count()).select_from(FareBreakdown).where(
                FareBreakdown.created_at >= month_start,
                FareBreakdown.ride_type.in_(["wheelchair_accessible", "stretcher"])
            )
            premium_result = await self.session.execute(premium_q)
            premium_count = premium_result.scalar() or 0
            premium_percent = Decimal(str(round(premium_count / total_rides * 100, 1)))

        return {
            "monthly_revenue": round(monthly_revenue, 2),
            "avg_trip_fare": round(avg_trip_fare, 2),
            "active_service_types": active_service_types,
            "premium_ride_percent": premium_percent,
        }

    async def get_route_comparison(self) -> list[dict]:
        configs = await self.config_repo.get_all(active_only=True)
        route_map: dict[str, dict] = {}

        for cfg in configs:
            config_data = cfg.config or {}
            route_pricing = config_data.get("route_pricing", {})
            for route_key, route_data in route_pricing.items():
                route_label = route_key.replace("_to_", " → ").replace("_", " ").title()
                if route_label not in route_map:
                    route_map[route_label] = {"route": route_label}
                route_map[route_label][cfg.service_type] = route_data.get("estimated_fare")

        return list(route_map.values())

    async def get_recent_changes(self, limit: int = 10) -> list[dict]:
        logs = await self.log_repo.get_recent(limit=limit)
        return [
            {
                "log_number": log.log_number,
                "admin_name": log.admin_name,
                "category": log.category,
                "change_description": log.change_description,
                "created_at": log.created_at,
            }
            for log in logs
        ]

    async def get_health(self) -> list[dict]:
        items = []

        # Check active rate card
        from app.repositories.rate_card_repo import RateCardRepository
        rc_repo = RateCardRepository(self.session)
        active_card = await rc_repo.get_active()
        if active_card:
            items.append({"label": "Active Rate Card", "status": "ok", "detail": f"Version {active_card.version}"})
        else:
            items.append({"label": "Active Rate Card", "status": "error", "detail": "No active rate card"})

        # Check service type configs
        configs = await self.config_repo.get_all(active_only=True)
        if len(configs) >= 3:
            items.append({"label": "Service Types", "status": "ok", "detail": f"{len(configs)} active"})
        else:
            items.append({"label": "Service Types", "status": "warning", "detail": f"Only {len(configs)} active"})

        # Check commission config
        from app.repositories.commission_config_repo import CommissionConfigRepository
        comm_repo = CommissionConfigRepository(self.session)
        active_comm = await comm_repo.get_active()
        if active_comm:
            items.append({"label": "Commission Config", "status": "ok", "detail": f"v{active_comm.version}"})
        else:
            items.append({"label": "Commission Config", "status": "error", "detail": "No active config"})

        # Check surcharge rules
        from app.repositories.surcharge_rule_repo import SurchargeRuleRepository
        sr_repo = SurchargeRuleRepository(self.session)
        active_surcharges = await sr_repo.count_active()
        items.append({"label": "Surcharge Rules", "status": "ok", "detail": f"{active_surcharges} active"})

        return items
