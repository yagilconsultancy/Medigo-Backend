import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.models.fare_breakdown import FareBreakdown
from app.repositories.dialysis_rate_plan_repo import DialysisRatePlanRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.holiday_repo import HolidayRepository
from app.repositories.rate_card_repo import RateCardRepository
from app.repositories.weather_condition_repo import WeatherConditionRepository

logger = logging.getLogger(__name__)

MILES_TO_KM = 1.60934
DEFAULT_TIMEZONE = "America/Toronto"


class FareService:
    def __init__(
        self,
        fare_repo: FareBreakdownRepository,
        rate_card_repo: RateCardRepository,
        holiday_repo: HolidayRepository,
        weather_repo: WeatherConditionRepository,
        dialysis_repo: DialysisRatePlanRepository,
    ):
        self.fare_repo = fare_repo
        self.rate_card_repo = rate_card_repo
        self.holiday_repo = holiday_repo
        self.weather_repo = weather_repo
        self.dialysis_repo = dialysis_repo

    async def calculate_fare(self, ride_data: dict) -> FareBreakdown:
        """Calculate fare for a completed ride and persist the breakdown."""
        result = await self._compute_fare(ride_data, persist=True)
        return result

    async def estimate_fare(self, ride_data: dict) -> dict:
        """Estimate fare without persisting. Returns a dict of the breakdown."""
        return await self._compute_fare(ride_data, persist=False)

    async def get_fare_breakdown(self, ride_id) -> FareBreakdown | None:
        return await self.fare_repo.get_by_ride_id(ride_id)

    async def _compute_fare(self, ride_data: dict, persist: bool = True):
        """Core fare computation logic used by both calculate and estimate."""
        # 1. Load active rate card
        rate_card = await self.rate_card_repo.get_active()
        if not rate_card:
            raise ValueError("No active rate card found. Cannot calculate fare.")
        config = rate_card.config

        tz_name = config.get("timezone", DEFAULT_TIMEZONE)
        tz = ZoneInfo(tz_name)

        # 2. Distance: convert miles → km
        distance_miles = float(ride_data.get("distance_miles", 0))
        distance_km = round(distance_miles * MILES_TO_KM, 2)

        # 3. Base fare calculation
        base_cfg = config.get("base_fare", {})
        flat_rate = float(base_cfg.get("flat_rate", 12.00))
        threshold_km = float(base_cfg.get("distance_threshold_km", 10.0))
        per_km_beyond = float(base_cfg.get("per_km_beyond_threshold", 0.75))

        distance_charge = 0.0
        if distance_km > threshold_km:
            distance_charge = round((distance_km - threshold_km) * per_km_beyond, 2)

        base_fare = flat_rate

        # 4. Wait time (completed rides only — from timeline)
        wait_time_minutes = _extract_wait_time(ride_data.get("timeline", []))
        wait_cfg = config.get("wait_time", {})
        free_minutes = int(wait_cfg.get("free_minutes", 10))
        per_min_rate = float(wait_cfg.get("per_minute_after_free", 0.50))
        billable_wait = max(0, wait_time_minutes - free_minutes)
        wait_time_charge = round(billable_wait * per_min_rate, 2)

        # 5. Determine ride local time for surcharge checks
        ride_dt = _get_ride_datetime(ride_data, tz)

        # 6. Accumulate surcharges
        surcharge_details = []
        surcharges_total = 0.0

        # 6a. Rush hour surcharges
        for rule in config.get("rush_hour_surcharges", []):
            if _rule_matches(ride_dt, rule):
                amount = float(rule["amount"])
                surcharges_total += amount
                surcharge_details.append({
                    "type": "rush_hour",
                    "name": rule["name"],
                    "amount": amount,
                })

        # 6b. Time-of-day surcharges
        for rule in config.get("time_of_day_surcharges", []):
            if _time_in_range(ride_dt.time(), rule["start"], rule["end"]):
                amount = float(rule["amount"])
                surcharges_total += amount
                surcharge_details.append({
                    "type": "time_of_day",
                    "name": rule["name"],
                    "amount": amount,
                })

        # 6c. Weekend surcharges
        weekend_cfg = config.get("weekend_surcharges", {})
        day_of_week = ride_dt.weekday()  # 0=Mon … 6=Sun
        if day_of_week == 5:  # Saturday
            amount = float(weekend_cfg.get("saturday", 0))
            if amount > 0:
                surcharges_total += amount
                surcharge_details.append({
                    "type": "weekend",
                    "name": "saturday",
                    "amount": amount,
                })
        elif day_of_week == 6:  # Sunday
            amount = float(weekend_cfg.get("sunday", 0))
            if amount > 0:
                surcharges_total += amount
                surcharge_details.append({
                    "type": "weekend",
                    "name": "sunday",
                    "amount": amount,
                })

        # 6d. Holiday surcharge
        is_holiday = await self.holiday_repo.is_holiday(ride_dt.date())
        if is_holiday:
            amount = float(config.get("holiday_surcharge", 5.00))
            surcharges_total += amount
            surcharge_details.append({
                "type": "holiday",
                "name": "public_holiday",
                "amount": amount,
            })

        # 6e. Weather surcharges (admin-toggled)
        active_weather = await self.weather_repo.get_active_conditions()
        weather_surcharges_cfg = config.get("weather_surcharges", {})
        for condition in active_weather:
            amount = float(weather_surcharges_cfg.get(condition.condition_type, 0))
            if amount > 0:
                surcharges_total += amount
                surcharge_details.append({
                    "type": "weather",
                    "name": condition.condition_type,
                    "amount": amount,
                })

        # 7. Apply surcharge cap
        max_cap = float(config.get("max_surcharge_cap", 18.00))
        surcharges_capped = min(surcharges_total, max_cap)

        # 8. Highway 407 toll (NOT subject to cap, pass-through)
        highway_407_toll = 0.0
        if ride_data.get("use_highway_407"):
            route = ride_data.get("highway_407_route", "")
            tolls_cfg = config.get("highway_407_tolls", {})
            highway_407_toll = float(tolls_cfg.get(route, 0))

        # 9. Fixed fees
        fees_cfg = config.get("fees", {})
        flat_surcharge = float(fees_cfg.get("surcharge_flat_per_trip", 0.06))
        insurance_gateway_fee = float(fees_cfg.get("insurance_payment_gateway_fee", 1.50))

        # 10. Dialysis rate override
        is_dialysis_rate = False
        dialysis_plan_id = None
        if ride_data.get("is_dialysis_trip"):
            plan = await self.dialysis_repo.get_matching_plan(
                origin=ride_data.get("pickup_address", ""),
                destination=ride_data.get("destination_address", ""),
            )
            if plan:
                is_dialysis_rate = True
                dialysis_plan_id = plan.id
                # Dialysis replaces base_fare + distance_charge only
                base_fare = float(plan.per_trip_rate)
                distance_charge = 0.0

        # 11. Compute totals
        subtotal = (
            base_fare
            + distance_charge
            + wait_time_charge
            + surcharges_capped
            + highway_407_toll
            + flat_surcharge
            + insurance_gateway_fee
        )

        platform_fee_pct = float(config.get("platform_fee_percent", 0.20))
        platform_fee = round(subtotal * platform_fee_pct, 2)
        total_fare = round(subtotal, 2)
        driver_earnings = round(total_fare - platform_fee, 2)

        # 12. Build result
        if persist:
            breakdown = FareBreakdown(
                ride_id=ride_data["ride_id"],
                base_fare=base_fare,
                distance_charge=distance_charge,
                medical_assist_premium=0,
                service_fee=0,
                platform_fee=platform_fee,
                tips=0,
                incentives_bonuses=0,
                total_fare=total_fare,
                driver_earnings=driver_earnings,
                distance_km=distance_km,
                wait_time_minutes=wait_time_minutes,
                wait_time_charge=wait_time_charge,
                surcharges_total=round(surcharges_total, 2),
                surcharges_capped=round(surcharges_capped, 2),
                surcharge_details=surcharge_details,
                highway_407_toll=highway_407_toll,
                insurance_gateway_fee=insurance_gateway_fee,
                flat_surcharge=flat_surcharge,
                is_dialysis_rate=is_dialysis_rate,
                dialysis_plan_id=dialysis_plan_id,
                rate_card_version=rate_card.version,
            )
            return await self.fare_repo.create(breakdown)
        else:
            # Return dict for estimate (no DB persistence)
            return {
                "base_fare": base_fare,
                "distance_km": distance_km,
                "distance_charge": distance_charge,
                "wait_time_minutes": wait_time_minutes,
                "wait_time_charge": wait_time_charge,
                "surcharges_total": round(surcharges_total, 2),
                "surcharges_capped": round(surcharges_capped, 2),
                "surcharge_details": surcharge_details,
                "highway_407_toll": highway_407_toll,
                "insurance_gateway_fee": insurance_gateway_fee,
                "flat_surcharge": flat_surcharge,
                "platform_fee": platform_fee,
                "total_fare": total_fare,
                "driver_earnings": driver_earnings,
                "is_dialysis_rate": is_dialysis_rate,
                "rate_card_version": rate_card.version,
            }


def _extract_wait_time(timeline: list[dict]) -> int:
    """Extract wait time minutes from status log timeline.

    Wait time = gap between driver_arrived and in_progress timestamps.
    """
    arrived_at = None
    started_at = None

    for entry in timeline:
        to_status = entry.get("to_status", "")
        ts = entry.get("timestamp")
        if to_status == "driver_arrived" and ts:
            arrived_at = _parse_timestamp(ts)
        elif to_status == "in_progress" and ts:
            started_at = _parse_timestamp(ts)

    if arrived_at and started_at and started_at > arrived_at:
        diff = (started_at - arrived_at).total_seconds()
        return int(diff // 60)
    return 0


def _parse_timestamp(ts) -> datetime | None:
    """Parse a timestamp that may be a string or datetime."""
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            return None
    return None


def _get_ride_datetime(ride_data: dict, tz: ZoneInfo) -> datetime:
    """Get the ride's local datetime for surcharge checks."""
    # Prefer pickup_at (actual), then scheduled_at, then now
    for field in ("pickup_at", "scheduled_at"):
        val = ride_data.get(field)
        if val:
            dt = _parse_timestamp(val)
            if dt:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                return dt.astimezone(tz)

    return datetime.now(tz)


def _rule_matches(ride_dt: datetime, rule: dict) -> bool:
    """Check if a rush hour rule matches the given local datetime."""
    allowed_days = rule.get("days", [])
    if ride_dt.weekday() not in allowed_days:
        return False
    return _time_in_range(ride_dt.time(), rule["start"], rule["end"])


def _time_in_range(current_time: time, start_str: str, end_str: str) -> bool:
    """Check if current_time falls within [start, end] (inclusive)."""
    start = time.fromisoformat(start_str)
    end = time.fromisoformat(end_str)
    if start <= end:
        return start <= current_time <= end
    else:
        # Wraps past midnight
        return current_time >= start or current_time <= end
