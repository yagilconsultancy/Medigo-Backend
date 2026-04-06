"""
Standalone seed script for payment-service pricing data.
Preloads all correct pricing configuration from official Medigo specs.

Run: python -m app.seed
"""
import asyncio
import json
import logging

from sqlalchemy import text

from app.config import settings
from mediride_common.database.base import get_async_engine, get_async_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed")

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


# ══════════════════════════════════════════════════════════════
# SERVICE TYPE CONFIGS — 5 entries (JSONB config per vehicle type)
# ══════════════════════════════════════════════════════════════

STANDARD_CONFIG = json.dumps({
    "rate_components": {
        "base_fare": 12.00,
        "base_fare_above_10km": 12.00,
        "per_km_beyond_10km": 0.75,
        "surcharge_flat": 0.06,
        "insurance_gateway_fee": 1.50,
        "free_wait_time_minutes": 10,
        "wait_time_per_min": 0.50,
        "max_surcharge_cap": 18.00
    },
    "distance_rules": {
        "base_distance_km": 10,
        "per_km_rate": 0.75,
        "description": "Flat $12 base for trips up to 10 km. $0.75 per km after 10 km."
    },
    "route_pricing": {
        "milton_local": {
            "label": "Milton Local",
            "distance_km": 8,
            "base_fare": 12.00,
            "avg_wait_charge": 1.00,
            "other_fees": 1.56,
            "typical_total": 14.56
        },
        "milton_to_georgetown": {
            "label": "Milton to Georgetown",
            "distance_km": 18,
            "base_fare": 18.00,
            "avg_wait_charge": 2.50,
            "other_fees": 1.56,
            "typical_total": 22.06
        },
        "milton_to_oakville": {
            "label": "Milton to Oakville",
            "distance_km": 26,
            "base_fare": 24.00,
            "avg_wait_charge": 10.00,
            "other_fees": 1.56,
            "typical_total": 35.56
        },
        "milton_to_burlington": {
            "label": "Milton to Burlington",
            "distance_km": 32,
            "base_fare": 28.50,
            "avg_wait_charge": 10.00,
            "other_fees": 1.56,
            "typical_total": 40.06
        },
        "milton_to_brampton": {
            "label": "Milton to Brampton",
            "distance_km": 38,
            "base_fare": 33.00,
            "avg_wait_charge": 10.00,
            "other_fees": 1.56,
            "typical_total": 44.56
        },
        "milton_to_mississauga": {
            "label": "Milton to Mississauga",
            "distance_km": 45,
            "base_fare": 38.25,
            "avg_wait_charge": 17.50,
            "other_fees": 1.56,
            "typical_total": 57.31
        }
    },
    "surcharges": {
        "weather": [
            {"condition": "Light snow / freezing rain", "surcharge": 3.00, "trigger": "Advisory"},
            {"condition": "Heavy snow / storm", "surcharge": 5.00, "trigger": "Storm warning"},
            {"condition": "Post-storm", "surcharge": 3.00, "trigger": "Within 24 hrs"}
        ],
        "rush_hour": [
            {"period": "7:00 am - 9:00 am", "days": "Mon-Fri", "surcharge": 4.00},
            {"period": "4:00 pm - 6:30 pm", "days": "Mon-Thu", "surcharge": 4.00},
            {"period": "4:00 pm - 7:00 pm", "days": "Friday", "surcharge": 5.00}
        ],
        "weekend_holiday": [
            {"day": "Saturday", "surcharge": 3.00},
            {"day": "Sunday", "surcharge": 4.00},
            {"day": "Ontario Public Holidays", "surcharge": 5.00}
        ],
        "time_based": [
            {"period": "Early Morning (5:00-6:59 am)", "surcharge": 5.00},
            {"period": "Late Night (9:00-11:59 pm)", "surcharge": 4.00},
            {"period": "Overnight (12:00-4:59 am)", "surcharge": 8.00}
        ]
    },
    "toll_charges": {
        "milton_to_oakville": {"surcharge": 8.00, "estimated_toll": "4.50-7.00"},
        "milton_to_brampton": {"surcharge": 9.00, "estimated_toll": "5.00-8.00"},
        "milton_to_mississauga": {"surcharge": 10.00, "estimated_toll": "6.00-9.00"}
    },
    "dialysis_discounts": {
        "description": "Reduced per-trip rates for recurring dialysis patients. See dialysis_rate_plans table."
    },
    "rules_and_caps": {
        "max_surcharge_cap": 18.00,
        "surcharge_stacking": True,
        "applies_per_trip": True
    }
})

WAV_CONFIG = json.dumps({
    "rate_components": {
        "base_fare": 22.00,
        "per_km_beyond_10km": 1.10,
        "accessibility_fee": 15.00,
        "minimum_fare_protection": 45.00,
        "surcharge_flat": 0.06,
        "insurance_gateway_fee": 1.50,
        "free_wait_time_minutes": 10,
        "wait_time_per_min": 0.80,
        "max_surcharge_cap": 18.00
    },
    "platform_commission": 0.18,
    "vendor_terms": {
        "commission_percent": 18,
        "accessibility_fee_passthrough": True,
        "onboarding_fee": 99.00,
        "off_platform_restriction_months": 12,
        "certification_required": "WAV certification, ramp/lift inspection records, accessible driver training"
    },
    "route_pricing": {
        "milton_local": {
            "label": "Milton Local",
            "distance_km": 8,
            "base_access": 37.00,
            "min_protected": 45.00,
            "wait": 8.00,
            "other_fees": 1.56,
            "total": 54.56
        },
        "milton_to_georgetown": {
            "label": "Milton to Georgetown",
            "distance_km": 18,
            "base_access": 45.80,
            "min_protected": 45.80,
            "wait": 8.00,
            "other_fees": 1.56,
            "total": 55.36
        },
        "milton_to_oakville": {
            "label": "Milton to Oakville",
            "distance_km": 26,
            "base_access": 54.60,
            "min_protected": 54.60,
            "wait": 16.00,
            "other_fees": 1.56,
            "total": 72.16
        },
        "milton_to_burlington": {
            "label": "Milton to Burlington",
            "distance_km": 32,
            "base_access": 61.20,
            "min_protected": 61.20,
            "wait": 16.00,
            "other_fees": 1.56,
            "total": 78.76
        },
        "milton_to_brampton": {
            "label": "Milton to Brampton",
            "distance_km": 38,
            "base_access": 67.80,
            "min_protected": 67.80,
            "wait": 16.00,
            "other_fees": 1.56,
            "total": 85.36
        },
        "milton_to_mississauga": {
            "label": "Milton to Mississauga",
            "distance_km": 45,
            "base_access": 75.50,
            "min_protected": 75.50,
            "wait": 28.00,
            "other_fees": 1.56,
            "total": 105.06
        }
    },
    "commission_breakdown": {
        "milton_local": {"total": 54.56, "medigo_18": 9.82, "vendor_82": 44.74},
        "milton_to_georgetown": {"total": 55.36, "medigo_18": 9.96, "vendor_82": 45.40},
        "milton_to_oakville": {"total": 72.16, "medigo_18": 12.99, "vendor_82": 59.17},
        "milton_to_burlington": {"total": 78.76, "medigo_18": 14.18, "vendor_82": 64.58},
        "milton_to_brampton": {"total": 85.36, "medigo_18": 15.36, "vendor_82": 70.00},
        "milton_to_mississauga": {"total": 105.06, "medigo_18": 18.91, "vendor_82": 86.15}
    }
})

STRETCHER_CONFIG = json.dumps({
    "rate_components": {
        "base_fare": 85.00,
        "per_km_beyond_10km": 2.25,
        "attendant_fee": 35.00,
        "surcharge_flat": 0.06,
        "insurance_gateway_fee": 1.50,
        "free_wait_time_minutes": 10,
        "wait_time_per_min": 1.00,
        "max_surcharge_cap": 18.00
    },
    "revenue_split": {
        "partnership_50_50": True,
        "operating_costs_deducted_first": True,
        "description": "Net after operating costs split 50/50 between partners"
    },
    "route_pricing": {
        "milton_local": {
            "label": "Milton Local",
            "distance_km": 8,
            "base_fare": 85.00,
            "attendant_fee": 35.00,
            "wait": 10.00,
            "other_fees": 1.56,
            "total": 131.56
        },
        "milton_to_georgetown": {
            "label": "Milton to Georgetown",
            "distance_km": 18,
            "base_fare": 103.00,
            "attendant_fee": 35.00,
            "wait": 10.00,
            "other_fees": 1.56,
            "total": 149.56
        },
        "milton_to_oakville": {
            "label": "Milton to Oakville",
            "distance_km": 26,
            "base_fare": 121.00,
            "attendant_fee": 35.00,
            "wait": 20.00,
            "other_fees": 1.56,
            "total": 177.56
        },
        "milton_to_burlington": {
            "label": "Milton to Burlington",
            "distance_km": 32,
            "base_fare": 134.50,
            "attendant_fee": 35.00,
            "wait": 20.00,
            "other_fees": 1.56,
            "total": 192.06
        },
        "milton_to_brampton": {
            "label": "Milton to Brampton",
            "distance_km": 38,
            "base_fare": 148.00,
            "attendant_fee": 35.00,
            "wait": 20.00,
            "other_fees": 1.56,
            "total": 205.56
        },
        "milton_to_mississauga": {
            "label": "Milton to Mississauga",
            "distance_km": 45,
            "base_fare": 163.75,
            "attendant_fee": 35.00,
            "wait": 35.00,
            "other_fees": 1.56,
            "total": 236.31
        }
    },
    "partnership_revenue": {
        "milton_local": {"total": 131.56, "op_costs": 55.00, "net": 76.56, "your_50": 38.28, "partner_50": 38.28},
        "milton_to_georgetown": {"total": 149.56, "op_costs": 62.00, "net": 87.56, "your_50": 43.78, "partner_50": 43.78},
        "milton_to_oakville": {"total": 177.56, "op_costs": 72.00, "net": 105.56, "your_50": 52.78, "partner_50": 52.78},
        "milton_to_burlington": {"total": 192.06, "op_costs": 78.00, "net": 114.06, "your_50": 57.03, "partner_50": 57.03},
        "milton_to_brampton": {"total": 205.56, "op_costs": 83.00, "net": 122.56, "your_50": 61.28, "partner_50": 61.28},
        "milton_to_mississauga": {"total": 236.31, "op_costs": 95.00, "net": 141.31, "your_50": 70.66, "partner_50": 70.66}
    }
})

PSW_CONFIG = json.dumps({
    "rate_components": {
        "standard_escort_hourly": 38.00,
        "additional_hours_hourly": 34.00,
        "minimum_booking_hours": 1,
        "free_wait_time_minutes": 0,
        "wait_time_per_min": 0
    },
    "terms": {
        "pre_booked_only": True,
        "cancellation_window_hours": 24,
        "provider": "SeniorHomeCare by Angels Milton",
        "description": "PSW accompanies patient, assists during transport and at appointment, provides home support on return. Not the driver — dedicated care worker."
    }
})

HOSPITAL_DISCHARGE_CONFIG = json.dumps({
    "package_overview": {
        "min_price": 220.00,
        "max_price": 280.00,
        "pricing_model": "flat_all_inclusive",
        "description": "Bundled all-inclusive package: stretcher transport + PSW escort during transport + 1hr home support. Quoted to families as a single flat price."
    },
    "components": {
        "stretcher_transport": {
            "range": "131-236",
            "provider": "Medigo Stretcher Vehicle",
            "description": "Door-to-door stretcher ride from hospital to home, driver + trained attendant"
        },
        "psw_escort_during_transport": {
            "description": "Trained PSW rides with patient from hospital room to home, provides comfort and monitoring",
            "provider": "SeniorHomeCare by Angels Milton",
            "fee": "Included"
        },
        "one_hour_home_support": {
            "description": "PSW stays 1 hour at home after arrival — settling in, safety check, medication reminder",
            "provider": "SeniorHomeCare by Angels Milton",
            "fee": "Included"
        }
    },
    "rate_components": {
        "free_wait_time_minutes": 0,
        "wait_time_per_min": 0
    },
    "developer_note": "This is a flat package price ($220-$280). Do NOT calculate from PSW escort hourly rate. Surface as bundle upgrade when client selects stretcher vehicle type during booking."
})


# ══════════════════════════════════════════════════════════════
# CANCELLATION POLICIES — 15 entries (3 service types × 5 windows)
# ══════════════════════════════════════════════════════════════

CANCELLATION_POLICIES = [
    # Ambulatory
    ("ambulatory", "24_hours_plus", 0, "none", "No charge applied", 1),
    ("ambulatory", "2_24_hours", 10.00, "medigo_platform", "Deducted from client account — 100% Medigo", 2),
    ("ambulatory", "under_2_hours", 20.00, "driver_80_medigo_20", "Driver compensated for lost trip — Driver 80% ($16), Medigo 20% ($4)", 3),
    ("ambulatory", "after_dispatch", 25.00, "driver_80_medigo_20", "Driver already en route — Driver 80% ($20), Medigo 20% ($5)", 4),
    ("ambulatory", "no_show", 35.00, "driver_80_medigo_20", "Full no-show penalty — Driver 80% ($28), Medigo 20% ($7)", 5),
    # WAV
    ("wheelchair_wav", "24_hours_plus", 0, "none", "No charge applied", 6),
    ("wheelchair_wav", "2_24_hours", 20.00, "vendor_82_medigo_18", "Vendor compensated for scheduling — Vendor 82%, Medigo 18%", 7),
    ("wheelchair_wav", "under_2_hours", 35.00, "vendor_82_medigo_18", "WAV pre-staged and ready — Vendor 82%, Medigo 18%", 8),
    ("wheelchair_wav", "after_dispatch", 45.00, "vendor_82_medigo_18", "Vehicle already dispatched — Vendor 82%, Medigo 18%", 9),
    ("wheelchair_wav", "no_show", 55.00, "vendor_82_medigo_18", "Full no-show — WAV arrived — Vendor 82%, Medigo 18%", 10),
    # Stretcher
    ("stretcher", "24_hours_plus", 0, "none", "No charge applied", 11),
    ("stretcher", "2_24_hours", 35.00, "partnership_50_50", "2-crew scheduling cost — Partnership split 50/50", 12),
    ("stretcher", "under_2_hours", 55.00, "partnership_50_50", "2-crew prepared and standing by — Partnership split 50/50", 13),
    ("stretcher", "after_dispatch", 70.00, "partnership_50_50", "2-crew already en route — Partnership split 50/50", 14),
    ("stretcher", "no_show", 85.00, "partnership_50_50", "Full no-show — 2 crew arrived — Partnership split 50/50", 15),
]


# ══════════════════════════════════════════════════════════════
# SURCHARGE RULES — 10 entries (flat dollar amounts, multiplier=1.0)
# ══════════════════════════════════════════════════════════════

SURCHARGE_RULES = [
    # (name, description, surcharge_type, multiplier, flat_amount, schedule_json, applies_to_json, is_active, sort_order)
    (
        "Peak Hours",
        "Mon-Fri 7-9 AM & 4-6:30 PM, Friday 4-7 PM = $5",
        "peak_hours", 1.0, 4.00,
        json.dumps({"periods": [
            {"days": [0, 1, 2, 3, 4], "start": "07:00", "end": "09:00"},
            {"days": [0, 1, 2, 3], "start": "16:00", "end": "18:30"},
            {"days": [4], "start": "16:00", "end": "19:00", "amount": 5.00},
        ]}),
        '["all"]', True, 1,
    ),
    (
        "Night Surcharge",
        "9:00 PM - 11:59 PM daily",
        "night", 1.0, 4.00,
        json.dumps({"periods": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "21:00", "end": "23:59"}]}),
        '["all"]', True, 2,
    ),
    (
        "Overnight",
        "12:00 AM - 4:59 AM daily",
        "overnight", 1.0, 8.00,
        json.dumps({"periods": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "00:00", "end": "04:59"}]}),
        '["all"]', True, 3,
    ),
    (
        "Early Morning",
        "5:00 AM - 6:59 AM daily",
        "early_morning", 1.0, 5.00,
        json.dumps({"periods": [{"days": [0, 1, 2, 3, 4, 5, 6], "start": "05:00", "end": "06:59"}]}),
        '["all"]', True, 4,
    ),
    (
        "Weather - Light Snow",
        "Active during light snow / freezing rain advisory",
        "weather_light_snow", 1.0, 3.00,
        None, '["all"]', False, 5,
    ),
    (
        "Weather - Heavy Snow",
        "Active during heavy snow / storm warning",
        "weather_heavy_snow", 1.0, 5.00,
        None, '["all"]', False, 6,
    ),
    (
        "Weather - Post Storm",
        "Active within 24 hrs after storm",
        "weather_post_storm", 1.0, 3.00,
        None, '["all"]', False, 7,
    ),
    (
        "Saturday",
        "Saturday surcharge",
        "weekend_saturday", 1.0, 3.00,
        json.dumps({"periods": [{"days": [5], "start": "00:00", "end": "23:59"}]}),
        '["all"]', True, 8,
    ),
    (
        "Sunday",
        "Sunday surcharge",
        "weekend_sunday", 1.0, 4.00,
        json.dumps({"periods": [{"days": [6], "start": "00:00", "end": "23:59"}]}),
        '["all"]', True, 9,
    ),
    (
        "Holiday Pricing",
        "Ontario statutory holidays — national & provincial",
        "holiday", 1.0, 5.00,
        None, '["all"]', True, 10,
    ),
]


# ══════════════════════════════════════════════════════════════
# DIALYSIS RATE PLANS — 4 entries (Milton-area routes)
# ══════════════════════════════════════════════════════════════

DIALYSIS_RATE_PLANS = [
    # (plan_name, origin, destination, per_trip_rate, monthly_package_rate, monthly_trips, min_per_week)
    ("Milton to Georgetown Dialysis", "Milton", "Georgetown", 18.00, 195.00, 12, 3),
    ("Milton to Oakville Dialysis", "Milton", "Oakville", 28.00, 300.00, 12, 3),
    ("Milton to Burlington Dialysis", "Milton", "Burlington", 32.00, 345.00, 12, 3),
    ("Milton to Mississauga Dialysis", "Milton", "Mississauga", 45.00, 490.00, 12, 3),
]


# ══════════════════════════════════════════════════════════════
# RIDE PACKAGES — 7 entries
# ══════════════════════════════════════════════════════════════

RIDE_PACKAGES = [
    # (name, description, package_type, price, ride_count, is_unlimited, discount_percent, validity_days, sort_order)
    ("10-Ride Bundle", "Save 7% on 10 rides. Perfect for regular appointments.", "rider", 79.00, 10, False, 7.00, 60, 1),
    ("20-Ride Bundle", "Save 14% on 20 rides. Great value for frequent riders.", "rider", 145.00, 20, False, 14.00, 90, 2),
    ("Monthly Unlimited", "Unlimited rides for 30 days. Best for daily commuters.", "subscription", 189.00, None, True, 20.00, 30, 3),
    ("Corporate Plan - 50", "50 rides for your organization. Volume discount included.", "corporate", 340.00, 50, False, 20.00, 120, 4),
    ("Corporate Plan - 100", "100 rides for larger organizations. Maximum savings.", "corporate", 620.00, 100, False, 27.00, 180, 5),
    ("Community Access", "Subsidized rides for community health programs.", "rider", 29.00, 10, False, 45.00, 90, 6),
    ("Medical VIP Monthly", "Priority unlimited rides with premium support.", "subscription", 249.00, None, True, 15.00, 30, 7),
]


# ══════════════════════════════════════════════════════════════
# SEED FUNCTIONS
# ══════════════════════════════════════════════════════════════

async def seed_cancellation_policies(session):
    """Seed 15 cancellation policies (3 service types x 5 windows)."""
    logger.info("Seeding cancellation_policies ...")
    await session.execute(text("DELETE FROM cancellation_policies"))

    for stype, window, fee, who, notes, sort in CANCELLATION_POLICIES:
        await session.execute(
            text("""
                INSERT INTO cancellation_policies
                    (service_type, cancellation_window, fee, who_receives, notes, sort_order)
                VALUES (:stype, :window, :fee, :who, :notes, :sort)
            """).bindparams(stype=stype, window=window, fee=fee, who=who, notes=notes, sort=sort)
        )

    logger.info("  -> 15 cancellation policies seeded")


async def seed_service_type_configs(session):
    """Seed 5 service type configs (Standard, WAV, Stretcher, PSW, Hospital Discharge)."""
    logger.info("Seeding service_type_configs ...")
    await session.execute(text("DELETE FROM service_type_configs"))

    configs = [
        ("standard", "Standard Vehicle", STANDARD_CONFIG, 1),
        ("wheelchair_wav", "Wheelchair (WAV)", WAV_CONFIG, 2),
        ("stretcher", "Stretcher Transport", STRETCHER_CONFIG, 3),
        ("psw_caregiver", "PSW / Caregiver", PSW_CONFIG, 4),
        ("hospital_discharge", "Hospital Discharge", HOSPITAL_DISCHARGE_CONFIG, 5),
    ]

    for stype, display, config, sort in configs:
        await session.execute(
            text("""
                INSERT INTO service_type_configs
                    (service_type, display_name, config, sort_order)
                VALUES (:stype, :display, CAST(:config AS jsonb), :sort)
            """).bindparams(stype=stype, display=display, config=config, sort=sort)
        )

    logger.info("  -> 5 service type configs seeded")


async def seed_surcharge_rules(session):
    """Seed 10 surcharge rules (flat dollar amounts, multiplier=1.0)."""
    logger.info("Seeding surcharge_rules ...")
    await session.execute(text("DELETE FROM surcharge_rules"))

    for name, desc, stype, mult, flat, schedule, applies, active, sort in SURCHARGE_RULES:
        if schedule is not None:
            await session.execute(
                text("""
                    INSERT INTO surcharge_rules
                        (name, description, surcharge_type, multiplier, flat_amount,
                         schedule, applies_to, is_active, sort_order)
                    VALUES (:name, :desc, :stype, :mult, :flat,
                            CAST(:schedule AS jsonb), CAST(:applies AS jsonb), :active, :sort)
                """).bindparams(
                    name=name, desc=desc, stype=stype, mult=mult, flat=flat,
                    schedule=schedule, applies=applies, active=active, sort=sort,
                )
            )
        else:
            await session.execute(
                text("""
                    INSERT INTO surcharge_rules
                        (name, description, surcharge_type, multiplier, flat_amount,
                         schedule, applies_to, is_active, sort_order)
                    VALUES (:name, :desc, :stype, :mult, :flat,
                            NULL, CAST(:applies AS jsonb), :active, :sort)
                """).bindparams(
                    name=name, desc=desc, stype=stype, mult=mult, flat=flat,
                    applies=applies, active=active, sort=sort,
                )
            )

    logger.info("  -> 10 surcharge rules seeded")


async def seed_dialysis_rate_plans(session):
    """Seed 4 Milton-area dialysis rate plans."""
    logger.info("Seeding dialysis_rate_plans ...")
    await session.execute(text("DELETE FROM dialysis_rate_plans"))

    for name, origin, dest, rate, monthly, trips, weekly in DIALYSIS_RATE_PLANS:
        await session.execute(
            text("""
                INSERT INTO dialysis_rate_plans
                    (id, plan_name, origin_area, destination_area, per_trip_rate,
                     monthly_package_rate, monthly_package_trips, min_trips_per_week,
                     is_active, created_by)
                VALUES (gen_random_uuid(), :name, :origin, :dest, :rate,
                        :monthly, :trips, :weekly,
                        true, CAST(:sys_user AS uuid))
            """).bindparams(
                name=name, origin=origin, dest=dest, rate=rate,
                monthly=monthly, trips=trips, weekly=weekly,
                sys_user=SYSTEM_USER_ID,
            )
        )

    logger.info("  -> 4 dialysis rate plans seeded")


async def seed_commission_configs(session):
    """Seed commission config v1 (18/47/20/10/5 split)."""
    logger.info("Seeding commission_configs ...")
    await session.execute(text("DELETE FROM commission_configs"))

    await session.execute(text("""
        INSERT INTO commission_configs
            (platform_percent, driver_percent, fleet_percent, caregiver_percent,
             reserve_percent, is_active, version)
        VALUES (18.00, 47.00, 20.00, 10.00, 5.00, true, 1)
    """))

    logger.info("  -> 1 commission config seeded (v1)")


async def seed_ride_packages(session):
    """Seed 7 ride packages."""
    logger.info("Seeding ride_packages ...")
    await session.execute(text("DELETE FROM ride_packages"))

    for name, desc, ptype, price, count, unlimited, discount, validity, sort in RIDE_PACKAGES:
        await session.execute(
            text("""
                INSERT INTO ride_packages
                    (name, description, package_type, price, ride_count,
                     is_unlimited, discount_percent, validity_days, sort_order)
                VALUES (:name, :desc, :ptype, :price, :count,
                        :unlimited, :discount, :validity, :sort)
            """).bindparams(
                name=name, desc=desc, ptype=ptype, price=price,
                count=count, unlimited=unlimited, discount=discount,
                validity=validity, sort=sort,
            )
        )

    logger.info("  -> 7 ride packages seeded")


# ══════════════════════════════════════════════════════════════
# INTERNAL SEED RUNNER (shared logic)
# ══════════════════════════════════════════════════════════════

async def _table_has_data(session, table_name: str) -> bool:
    """Check if a table already has rows."""
    result = await session.execute(text(f"SELECT EXISTS(SELECT 1 FROM {table_name} LIMIT 1)"))
    return result.scalar()


async def _run_seed_with_session(session, force: bool = False):
    """Run seed functions — only seeds tables that are empty.
    If force=True, wipes and re-inserts everything (CLI --force mode).
    """
    if force:
        await seed_cancellation_policies(session)
        await seed_service_type_configs(session)
        await seed_surcharge_rules(session)
        await seed_dialysis_rate_plans(session)
        await seed_commission_configs(session)
        await seed_ride_packages(session)
        return

    # Only seed empty tables — preserve admin changes
    if not await _table_has_data(session, "cancellation_policies"):
        await seed_cancellation_policies(session)
    else:
        logger.info("Skipping cancellation_policies — already has data")

    if not await _table_has_data(session, "service_type_configs"):
        await seed_service_type_configs(session)
    else:
        logger.info("Skipping service_type_configs — already has data")

    if not await _table_has_data(session, "surcharge_rules"):
        await seed_surcharge_rules(session)
    else:
        logger.info("Skipping surcharge_rules — already has data")

    if not await _table_has_data(session, "dialysis_rate_plans"):
        await seed_dialysis_rate_plans(session)
    else:
        logger.info("Skipping dialysis_rate_plans — already has data")

    if not await _table_has_data(session, "commission_configs"):
        await seed_commission_configs(session)
    else:
        logger.info("Skipping commission_configs — already has data")

    if not await _table_has_data(session, "ride_packages"):
        await seed_ride_packages(session)
    else:
        logger.info("Skipping ride_packages — already has data")


# ══════════════════════════════════════════════════════════════
# STARTUP HOOK — called from main.py lifespan on every restart
# ══════════════════════════════════════════════════════════════

async def run_seed():
    """Run seed using the already-initialized DB from dependencies.
    Called automatically during app startup (lifespan).
    Safe to run on every restart — uses DELETE + INSERT (idempotent).
    """
    from app.dependencies import get_db

    logger.info("=" * 60)
    logger.info("MediGo Payment Service — Auto-seeding pricing data ...")
    logger.info("=" * 60)

    async for session in get_db():
        try:
            await _run_seed_with_session(session)
            logger.info("=" * 60)
            logger.info("All pricing data seeded successfully!")
            logger.info("=" * 60)
        except Exception:
            logger.exception("Seed failed during startup")
            raise


# ══════════════════════════════════════════════════════════════
# CLI ENTRY POINT — python -m app.seed
# ══════════════════════════════════════════════════════════════

async def seed_all(force: bool = False):
    """Connect to DB directly and seed all pricing tables.
    For standalone CLI usage:
        python -m app.seed          # only seeds empty tables
        python -m app.seed --force  # wipes and re-inserts everything
    """
    mode = "FORCE (wipe + reseed)" if force else "safe (skip existing)"
    logger.info("=" * 60)
    logger.info(f"MediGo Payment Service — Pricing Data Seed (CLI) [{mode}]")
    logger.info("=" * 60)

    engine = get_async_engine(settings.DATABASE_URL)
    session_factory = get_async_session_factory(engine)

    async with session_factory() as session:
        try:
            await _run_seed_with_session(session, force=force)
            await session.commit()
            logger.info("=" * 60)
            logger.info("All pricing data seeded successfully!")
            logger.info("=" * 60)
        except Exception:
            await session.rollback()
            logger.exception("Seed failed — rolled back")
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    import sys
    force_mode = "--force" in sys.argv
    asyncio.run(seed_all(force=force_mode))
