import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.models.fare_breakdown import FareBreakdown
from app.repositories.dialysis_rate_plan_repo import DialysisRatePlanRepository
from app.repositories.fare_repo import FareBreakdownRepository
from app.repositories.holiday_repo import HolidayRepository
from app.repositories.rate_card_repo import RateCardRepository
from app.repositories.service_type_config_repo import ServiceTypeConfigRepository
from app.repositories.weather_condition_repo import WeatherConditionRepository

logger = logging.getLogger(__name__)

MILES_TO_KM = 1.60934
DEFAULT_TIMEZONE = "America/Toronto"

# Map ride_type enum values to service_type_configs.service_type keys
_RIDE_TYPE_TO_SERVICE_TYPE = {
    "ambulatory": "standard",
    "standard": "standard",
    "wheelchair": "wheelchair_wav",
    "stretcher": "stretcher",
}

DEFAULT_CARE_ASSISTANT_FEE = 35.00


class FareService:
    def __init__(
        self,
        fare_repo: FareBreakdownRepository,
        rate_card_repo: RateCardRepository,
        holiday_repo: HolidayRepository,
        weather_repo: WeatherConditionRepository,
        dialysis_repo: DialysisRatePlanRepository,
        service_type_repo: ServiceTypeConfigRepository | None = None,
    ):
        self.fare_repo = fare_repo
        self.rate_card_repo = rate_card_repo
        self.holiday_repo = holiday_repo
        self.weather_repo = weather_repo
        self.dialysis_repo = dialysis_repo
        self.service_type_repo = service_type_repo

    async def calculate_fare(self, ride_data: dict) -> FareBreakdown:
        """Calculate fare for a completed ride and persist the breakdown."""
        result = await self._compute_fare(ride_data, persist=True)
        return result

    async def estimate_fare(self, ride_data: dict) -> dict:
        """Estimate fare without persisting. Returns a dict of the breakdown."""
        return await self._compute_fare(ride_data, persist=False)

    async def get_fare_breakdown(self, ride_id) -> FareBreakdown | None:
        return await self.fare_repo.get_by_ride_id(ride_id)

    async def _resolve_service_rates(self, ride_type: str, rate_card_config: dict) -> dict:
        """Load per-ride-type rates from ServiceTypeConfig, falling back to rate card defaults."""
        defaults = {
            "base_fare": float(rate_card_config.get("base_fare", {}).get("flat_rate", 12.00)),
            "threshold_km": float(rate_card_config.get("base_fare", {}).get("distance_threshold_km", 10.0)),
            "per_km_beyond": float(rate_card_config.get("base_fare", {}).get("per_km_beyond_threshold", 0.75)),
            "free_wait_minutes": int(rate_card_config.get("wait_time", {}).get("free_minutes", 10)),
            "wait_per_min": float(rate_card_config.get("wait_time", {}).get("per_minute_after_free", 0.50)),
            "accessibility_fee": 0.0,
            "attendant_fee": 0.0,
            "minimum_fare_protection": 0.0,
            "service_type_key": "standard",
        }

        service_type_key = _RIDE_TYPE_TO_SERVICE_TYPE.get(ride_type, "standard")
        defaults["service_type_key"] = service_type_key

        if not self.service_type_repo:
            return defaults

        stc = await self.service_type_repo.get_by_service_type(service_type_key)
        if not stc or not stc.config:
            return defaults

        rc = stc.config.get("rate_components", {})
        if not rc:
            return defaults

        return {
            "base_fare": float(rc.get("base_fare", defaults["base_fare"])),
            "threshold_km": float(rc.get("base_distance_km", defaults["threshold_km"])),
            "per_km_beyond": float(rc.get("per_km_beyond_10km", defaults["per_km_beyond"])),
            "free_wait_minutes": int(rc.get("free_wait_time_minutes", defaults["free_wait_minutes"])),
            "wait_per_min": float(rc.get("wait_time_per_min", defaults["wait_per_min"])),
            "accessibility_fee": float(rc.get("accessibility_fee", 0.0)),
            "attendant_fee": float(rc.get("attendant_fee", 0.0)),
            "minimum_fare_protection": float(rc.get("minimum_fare_protection", 0.0)),
            "service_type_key": service_type_key,
        }

    async def _compute_fare(self, ride_data: dict, persist: bool = True):
        """Core fare computation logic used by both calculate and estimate."""
        # 1. Load active rate card (used for surcharge rules, highway tolls, fees, platform %)
        rate_card = await self.rate_card_repo.get_active()
        if not rate_card:
            raise ValueError("No active rate card found. Cannot calculate fare.")
        config = rate_card.config

        tz_name = config.get("timezone", DEFAULT_TIMEZONE)
        tz = ZoneInfo(tz_name)

        # 2. Resolve per-ride-type rates from ServiceTypeConfig
        ride_type = ride_data.get("ride_type", "ambulatory")
        trip_type = ride_data.get("trip_type", "transport_only")
        trip_structure = ride_data.get("trip_structure", "one_way")
        is_round_trip = trip_structure == "round_trip"

        rates = await self._resolve_service_rates(ride_type, config)

        # 3. Distance: convert miles → km
        distance_miles = float(ride_data.get("distance_miles", 0))
        distance_km = round(distance_miles * MILES_TO_KM, 2)

        # 4. Base fare + distance charge using service-type rates
        base_fare = rates["base_fare"]
        threshold_km = rates["threshold_km"]
        per_km_beyond = rates["per_km_beyond"]

        distance_charge = 0.0
        if distance_km > threshold_km:
            distance_charge = round((distance_km - threshold_km) * per_km_beyond, 2)

        # 5. Wait time using service-type rates
        wait_time_minutes = _extract_wait_time(ride_data.get("timeline", []))
        free_minutes = rates["free_wait_minutes"]
        per_min_rate = rates["wait_per_min"]
        billable_wait = max(0, wait_time_minutes - free_minutes)
        wait_time_charge = round(billable_wait * per_min_rate, 2)

        # 6. Type-specific fees
        accessibility_fee = rates["accessibility_fee"]
        attendant_fee = rates["attendant_fee"]

        # 7. Care assistant fee — only for scheduled trips with TRANSPORT_CARE_ASSISTANT
        care_assistant_fee = 0.0
        if trip_type == "transport_care_assistant":
            scheduled_at = ride_data.get("scheduled_at")
            if scheduled_at:
                care_assistant_fee = DEFAULT_CARE_ASSISTANT_FEE

        # 8. Determine ride local time for surcharge checks
        ride_dt = _get_ride_datetime(ride_data, tz)

        # 9. Accumulate surcharges (from rate card — same for all service types)
        surcharge_details = []
        surcharges_total = 0.0

        # 9a. Rush hour surcharges
        for rule in config.get("rush_hour_surcharges", []):
            if _rule_matches(ride_dt, rule):
                amount = float(rule["amount"])
                surcharges_total += amount
                surcharge_details.append({
                    "type": "rush_hour",
                    "name": rule["name"],
                    "amount": amount,
                })

        # 9b. Time-of-day surcharges
        for rule in config.get("time_of_day_surcharges", []):
            if _time_in_range(ride_dt.time(), rule["start"], rule["end"]):
                amount = float(rule["amount"])
                surcharges_total += amount
                surcharge_details.append({
                    "type": "time_of_day",
                    "name": rule["name"],
                    "amount": amount,
                })

        # 9c. Weekend surcharges
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

        # 9d. Holiday surcharge
        is_holiday = await self.holiday_repo.is_holiday(ride_dt.date())
        if is_holiday:
            amount = float(config.get("holiday_surcharge", 5.00))
            surcharges_total += amount
            surcharge_details.append({
                "type": "holiday",
                "name": "public_holiday",
                "amount": amount,
            })

        # 9e. Weather surcharges (admin-toggled)
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

        # 10. Apply surcharge cap
        max_cap = float(config.get("max_surcharge_cap", 18.00))
        surcharges_capped = min(surcharges_total, max_cap)

        # 11. Highway 407 toll (NOT subject to cap, pass-through)
        highway_407_toll = 0.0
        if ride_data.get("use_highway_407"):
            route = ride_data.get("highway_407_route", "")
            tolls_cfg = config.get("highway_407_tolls", {})
            highway_407_toll = float(tolls_cfg.get(route, 0))

        # 12. Fixed fees
        fees_cfg = config.get("fees", {})
        flat_surcharge = float(fees_cfg.get("surcharge_flat_per_trip", 0.06))
        insurance_gateway_fee = float(fees_cfg.get("insurance_payment_gateway_fee", 1.50))

        # 13. Dialysis rate override
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

        # 14. One-way subtotal
        one_way_subtotal = (
            base_fare
            + distance_charge
            + wait_time_charge
            + accessibility_fee
            + attendant_fee
            + care_assistant_fee
            + surcharges_capped
            + highway_407_toll
            + flat_surcharge
            + insurance_gateway_fee
        )

        # 15. WAV minimum fare protection
        min_fare = rates["minimum_fare_protection"]
        if min_fare > 0 and one_way_subtotal < min_fare:
            one_way_subtotal = min_fare

        # 16. Round trip: add return leg (base + distance again)
        return_distance_charge = 0.0
        if is_round_trip:
            return_distance_charge = distance_charge
            total_fare_raw = one_way_subtotal + base_fare + return_distance_charge
        else:
            total_fare_raw = one_way_subtotal

        # 17. Platform fee & earnings
        platform_fee_pct = float(config.get("platform_fee_percent", 0.20))
        platform_fee = round(total_fare_raw * platform_fee_pct, 2)
        total_fare = round(total_fare_raw, 2)
        driver_earnings = round(total_fare - platform_fee, 2)

        # 18. Build result
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
                business_id=ride_data.get("business_id"),
                driver_id=ride_data.get("driver_id"),
                ride_type=ride_data.get("ride_type"),
                pickup_city=ride_data.get("pickup_city"),
                care_assistant_fee=care_assistant_fee,
                accessibility_fee=accessibility_fee,
                attendant_fee=attendant_fee,
                trip_type=trip_type,
                trip_structure=trip_structure,
                is_round_trip=is_round_trip,
                return_distance_charge=return_distance_charge,
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
                "care_assistant_fee": care_assistant_fee,
                "accessibility_fee": accessibility_fee,
                "attendant_fee": attendant_fee,
                "is_round_trip": is_round_trip,
                "return_distance_charge": return_distance_charge,
                "ride_type": ride_type,
                "trip_type": trip_type,
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
