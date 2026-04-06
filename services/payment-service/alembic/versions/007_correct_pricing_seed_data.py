"""Correct pricing seed data to match official Medigo PDF specifications.

Fixes all wrong values from migration 006:
- Cancellation policies: corrects fees and who_receives splits
- Service type configs: corrects all 5 JSONB configs (rates, routes, wait time)
- Surcharge rules: replaces 6 multiplier-based with 10 flat-dollar rules
- Dialysis rate plans: seeds 4 Milton-area plans (table was empty)

Revision ID: 007
Revises: 006
Create Date: 2026-04-06
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    _fix_cancellation_policies()
    _fix_service_type_configs()
    _fix_surcharge_rules()
    _seed_dialysis_rate_plans()


def downgrade() -> None:
    _revert_cancellation_policies()
    _revert_service_type_configs()
    _revert_surcharge_rules()
    op.execute(sa.text("DELETE FROM dialysis_rate_plans"))


# ──────────────────────────────────────────────────────────────
# CANCELLATION POLICIES
# ──────────────────────────────────────────────────────────────

def _fix_cancellation_policies():
    """Update all 15 cancellation policies to match official PDF specs."""
    updates = [
        # Ambulatory — 24hrs+ stays the same (fee=0, none)
        ("ambulatory", "24_hours_plus", 0, "none", "No charge applied"),
        ("ambulatory", "2_24_hours", 10.00, "medigo_platform",
         "Deducted from client account — 100% Medigo"),
        ("ambulatory", "under_2_hours", 20.00, "driver_80_medigo_20",
         "Driver compensated for lost trip — Driver 80% ($16), Medigo 20% ($4)"),
        ("ambulatory", "after_dispatch", 25.00, "driver_80_medigo_20",
         "Driver already en route — Driver 80% ($20), Medigo 20% ($5)"),
        ("ambulatory", "no_show", 35.00, "driver_80_medigo_20",
         "Full no-show penalty — Driver 80% ($28), Medigo 20% ($7)"),
        # WAV
        ("wheelchair_wav", "24_hours_plus", 0, "none", "No charge applied"),
        ("wheelchair_wav", "2_24_hours", 20.00, "vendor_82_medigo_18",
         "Vendor compensated for scheduling — Vendor 82%, Medigo 18%"),
        ("wheelchair_wav", "under_2_hours", 35.00, "vendor_82_medigo_18",
         "WAV pre-staged and ready — Vendor 82%, Medigo 18%"),
        ("wheelchair_wav", "after_dispatch", 45.00, "vendor_82_medigo_18",
         "Vehicle already dispatched — Vendor 82%, Medigo 18%"),
        ("wheelchair_wav", "no_show", 55.00, "vendor_82_medigo_18",
         "Full no-show — WAV arrived — Vendor 82%, Medigo 18%"),
        # Stretcher
        ("stretcher", "24_hours_plus", 0, "none", "No charge applied"),
        ("stretcher", "2_24_hours", 35.00, "partnership_50_50",
         "2-crew scheduling cost — Partnership split 50/50"),
        ("stretcher", "under_2_hours", 55.00, "partnership_50_50",
         "2-crew prepared and standing by — Partnership split 50/50"),
        ("stretcher", "after_dispatch", 70.00, "partnership_50_50",
         "2-crew already en route — Partnership split 50/50"),
        ("stretcher", "no_show", 85.00, "partnership_50_50",
         "Full no-show — 2 crew arrived — Partnership split 50/50"),
    ]
    for stype, window, fee, who, notes in updates:
        op.execute(sa.text("""
            UPDATE cancellation_policies
            SET fee = :fee, who_receives = :who, notes = :notes, updated_at = NOW()
            WHERE service_type = :stype AND cancellation_window = :window
        """).bindparams(stype=stype, window=window, fee=fee, who=who, notes=notes))


def _revert_cancellation_policies():
    """Revert to old migration 006 values."""
    old_values = [
        ("ambulatory", "24_hours_plus", 0, "none", "Full refund, no fee charged"),
        ("ambulatory", "2_24_hours", 15.00, "medigo_platform", "Administrative fee only"),
        ("ambulatory", "under_2_hours", 25.00, "driver_80_medigo_20",
         "Driver receives 80% ($20), MediGo receives 20% ($5)"),
        ("ambulatory", "after_dispatch", 35.00, "driver_80_medigo_20",
         "Driver receives 80% ($28), MediGo receives 20% ($7)"),
        ("ambulatory", "no_show", 45.00, "driver_85_medigo_15",
         "Driver receives 85% ($38.25), MediGo receives 15% ($6.75)"),
        ("wheelchair_wav", "24_hours_plus", 0, "none", "Full refund, no fee charged"),
        ("wheelchair_wav", "2_24_hours", 25.00, "medigo_platform",
         "Higher admin fee due to specialized vehicle"),
        ("wheelchair_wav", "under_2_hours", 45.00, "driver_70_vendor_20_medigo_10",
         "Split: Driver 70%, WAV vendor 20%, MediGo 10%"),
        ("wheelchair_wav", "after_dispatch", 65.00, "driver_70_vendor_20_medigo_10",
         "Split: Driver 70%, WAV vendor 20%, MediGo 10%"),
        ("wheelchair_wav", "no_show", 85.00, "driver_70_vendor_25_medigo_5",
         "Split: Driver 70%, WAV vendor 25%, MediGo 5%"),
        ("stretcher", "24_hours_plus", 0, "none", "Full refund, no fee charged"),
        ("stretcher", "2_24_hours", 50.00, "medigo_platform",
         "Higher admin fee due to crew + equipment"),
        ("stretcher", "under_2_hours", 85.00, "company_75_medigo_25",
         "Transport company receives 75%, MediGo 25%"),
        ("stretcher", "after_dispatch", 120.00, "company_80_medigo_20",
         "Transport company receives 80%, MediGo 20%"),
        ("stretcher", "no_show", 150.00, "company_85_medigo_15",
         "Transport company receives 85%, MediGo 15%"),
    ]
    for stype, window, fee, who, notes in old_values:
        op.execute(sa.text("""
            UPDATE cancellation_policies
            SET fee = :fee, who_receives = :who, notes = :notes, updated_at = NOW()
            WHERE service_type = :stype AND cancellation_window = :window
        """).bindparams(stype=stype, window=window, fee=fee, who=who, notes=notes))


# ──────────────────────────────────────────────────────────────
# SERVICE TYPE CONFIGS
# ──────────────────────────────────────────────────────────────

_STANDARD_CONFIG = json.dumps({
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
        "milton_local": {"label": "Milton Local", "distance_km": 8, "base_fare": 12.00, "avg_wait_charge": 1.00, "other_fees": 1.56, "typical_total": 14.56},
        "milton_to_georgetown": {"label": "Milton to Georgetown", "distance_km": 18, "base_fare": 18.00, "avg_wait_charge": 2.50, "other_fees": 1.56, "typical_total": 22.06},
        "milton_to_oakville": {"label": "Milton to Oakville", "distance_km": 26, "base_fare": 24.00, "avg_wait_charge": 10.00, "other_fees": 1.56, "typical_total": 35.56},
        "milton_to_burlington": {"label": "Milton to Burlington", "distance_km": 32, "base_fare": 28.50, "avg_wait_charge": 10.00, "other_fees": 1.56, "typical_total": 40.06},
        "milton_to_brampton": {"label": "Milton to Brampton", "distance_km": 38, "base_fare": 33.00, "avg_wait_charge": 10.00, "other_fees": 1.56, "typical_total": 44.56},
        "milton_to_mississauga": {"label": "Milton to Mississauga", "distance_km": 45, "base_fare": 38.25, "avg_wait_charge": 17.50, "other_fees": 1.56, "typical_total": 57.31}
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

_WAV_CONFIG = json.dumps({
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
        "milton_local": {"label": "Milton Local", "distance_km": 8, "base_access": 37.00, "min_protected": 45.00, "wait": 8.00, "other_fees": 1.56, "total": 54.56},
        "milton_to_georgetown": {"label": "Milton to Georgetown", "distance_km": 18, "base_access": 45.80, "min_protected": 45.80, "wait": 8.00, "other_fees": 1.56, "total": 55.36},
        "milton_to_oakville": {"label": "Milton to Oakville", "distance_km": 26, "base_access": 54.60, "min_protected": 54.60, "wait": 16.00, "other_fees": 1.56, "total": 72.16},
        "milton_to_burlington": {"label": "Milton to Burlington", "distance_km": 32, "base_access": 61.20, "min_protected": 61.20, "wait": 16.00, "other_fees": 1.56, "total": 78.76},
        "milton_to_brampton": {"label": "Milton to Brampton", "distance_km": 38, "base_access": 67.80, "min_protected": 67.80, "wait": 16.00, "other_fees": 1.56, "total": 85.36},
        "milton_to_mississauga": {"label": "Milton to Mississauga", "distance_km": 45, "base_access": 75.50, "min_protected": 75.50, "wait": 28.00, "other_fees": 1.56, "total": 105.06}
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

_STRETCHER_CONFIG = json.dumps({
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
        "milton_local": {"label": "Milton Local", "distance_km": 8, "base_fare": 85.00, "attendant_fee": 35.00, "wait": 10.00, "other_fees": 1.56, "total": 131.56},
        "milton_to_georgetown": {"label": "Milton to Georgetown", "distance_km": 18, "base_fare": 103.00, "attendant_fee": 35.00, "wait": 10.00, "other_fees": 1.56, "total": 149.56},
        "milton_to_oakville": {"label": "Milton to Oakville", "distance_km": 26, "base_fare": 121.00, "attendant_fee": 35.00, "wait": 20.00, "other_fees": 1.56, "total": 177.56},
        "milton_to_burlington": {"label": "Milton to Burlington", "distance_km": 32, "base_fare": 134.50, "attendant_fee": 35.00, "wait": 20.00, "other_fees": 1.56, "total": 192.06},
        "milton_to_brampton": {"label": "Milton to Brampton", "distance_km": 38, "base_fare": 148.00, "attendant_fee": 35.00, "wait": 20.00, "other_fees": 1.56, "total": 205.56},
        "milton_to_mississauga": {"label": "Milton to Mississauga", "distance_km": 45, "base_fare": 163.75, "attendant_fee": 35.00, "wait": 35.00, "other_fees": 1.56, "total": 236.31}
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

_PSW_CONFIG = json.dumps({
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

_DISCHARGE_CONFIG = json.dumps({
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


def _fix_service_type_configs():
    """Update all 5 service type configs with correct JSONB from official specs."""
    configs = [
        ("standard", _STANDARD_CONFIG),
        ("wheelchair_wav", _WAV_CONFIG),
        ("stretcher", _STRETCHER_CONFIG),
        ("psw_caregiver", _PSW_CONFIG),
        ("hospital_discharge", _DISCHARGE_CONFIG),
    ]
    for stype, config_json in configs:
        op.execute(sa.text("""
            UPDATE service_type_configs
            SET config = CAST(:config AS jsonb), updated_at = NOW()
            WHERE service_type = :stype
        """).bindparams(stype=stype, config=config_json))


def _revert_service_type_configs():
    """Revert to old migration 006 configs."""
    old_configs = [
        ("standard",
         '{"rate_components":{"base_fare":12.00,"per_km_rate":2.20,"booking_fee":3.50,"wait_time_per_min":0.45,"minimum_fare":15.00},"distance_rules":{"short_trip_km":5,"medium_trip_km":25,"long_trip_km":50},"route_pricing":{"toronto_to_hamilton":{"distance_km":70,"estimated_fare":166.50},"toronto_to_mississauga":{"distance_km":30,"estimated_fare":78.50},"toronto_to_brampton":{"distance_km":40,"estimated_fare":100.50},"toronto_to_markham":{"distance_km":32,"estimated_fare":82.90},"toronto_to_scarborough":{"distance_km":20,"estimated_fare":56.50},"hamilton_to_burlington":{"distance_km":15,"estimated_fare":45.50},"ottawa_to_gatineau":{"distance_km":12,"estimated_fare":38.90}},"toll_charges":{"highway_407":{"per_km":0.25,"minimum":2.50}},"dialysis_discounts":{"discount_percent":15,"max_discount":25.00}}'),
        ("wheelchair_wav",
         '{"rate_components":{"base_fare":22.00,"per_km_rate":2.80,"accessibility_fee":15.00,"booking_fee":3.50,"wait_time_per_min":0.55,"minimum_fare":45.00},"platform_commission":0.18,"vendor_terms":{"cancellation_window_hours":24,"late_cancellation_fee":35.00,"no_show_fee":45.00},"route_pricing":{"toronto_to_hamilton":{"distance_km":70,"estimated_fare":234.50},"toronto_to_mississauga":{"distance_km":30,"estimated_fare":124.50},"toronto_to_brampton":{"distance_km":40,"estimated_fare":152.50}}}'),
        ("stretcher",
         '{"rate_components":{"base_fare":85.00,"per_km_rate":4.50,"attendant_fee":35.00,"equipment_fee":25.00,"booking_fee":5.00,"wait_time_per_min":0.75,"minimum_fare":150.00},"revenue_split":{"platform":0.18,"transport_company":0.82},"partnership_terms":{"insurance_required":true,"min_vehicles":2,"certification":"Ontario Stretcher Transport License"}}'),
        ("psw_caregiver",
         '{"service_rates":{"hourly_rate":32.00,"half_day_rate":120.00,"full_day_rate":220.00,"overnight_rate":180.00,"weekend_premium":1.25},"terms":{"minimum_booking_hours":2,"cancellation_window_hours":12,"late_cancellation_fee":25.00}}'),
        ("hospital_discharge",
         '{"package_overview":{"base_price":89.00,"includes":"Transport + 1hr wait + wheelchair assist"},"components":{"transport_base":55.00,"wait_time_included_min":60,"additional_wait_per_min":0.50,"wheelchair_assist":15.00,"medication_pickup":19.00,"pharmacy_stop":12.00}}'),
    ]
    for stype, config_json in old_configs:
        op.execute(sa.text("""
            UPDATE service_type_configs
            SET config = CAST(:config AS jsonb), updated_at = NOW()
            WHERE service_type = :stype
        """).bindparams(stype=stype, config=config_json))


# ──────────────────────────────────────────────────────────────
# SURCHARGE RULES
# ──────────────────────────────────────────────────────────────

def _fix_surcharge_rules():
    """Replace 6 multiplier-based rules with 10 flat-dollar rules."""
    op.execute(sa.text("DELETE FROM surcharge_rules"))

    op.execute(sa.text("""
        INSERT INTO surcharge_rules
            (name, description, surcharge_type, multiplier, flat_amount,
             schedule, applies_to, is_active, sort_order)
        VALUES
            ('Peak Hours', 'Mon-Fri 7-9 AM & 4-6:30 PM, Friday 4-7 PM = $5',
             'peak_hours', 1.0, 4.00, CAST(:peak_sched AS jsonb),
             CAST(:all_types AS jsonb), true, 1),
            ('Night Surcharge', '9:00 PM - 11:59 PM daily',
             'night', 1.0, 4.00, CAST(:night_sched AS jsonb),
             CAST(:all_types AS jsonb), true, 2),
            ('Overnight', '12:00 AM - 4:59 AM daily',
             'overnight', 1.0, 8.00, CAST(:overnight_sched AS jsonb),
             CAST(:all_types AS jsonb), true, 3),
            ('Early Morning', '5:00 AM - 6:59 AM daily',
             'early_morning', 1.0, 5.00, CAST(:early_sched AS jsonb),
             CAST(:all_types AS jsonb), true, 4),
            ('Weather - Light Snow', 'Active during light snow / freezing rain advisory',
             'weather_light_snow', 1.0, 3.00, NULL,
             CAST(:all_types AS jsonb), false, 5),
            ('Weather - Heavy Snow', 'Active during heavy snow / storm warning',
             'weather_heavy_snow', 1.0, 5.00, NULL,
             CAST(:all_types AS jsonb), false, 6),
            ('Weather - Post Storm', 'Active within 24 hrs after storm',
             'weather_post_storm', 1.0, 3.00, NULL,
             CAST(:all_types AS jsonb), false, 7),
            ('Saturday', 'Saturday surcharge',
             'weekend_saturday', 1.0, 3.00, CAST(:sat_sched AS jsonb),
             CAST(:all_types AS jsonb), true, 8),
            ('Sunday', 'Sunday surcharge',
             'weekend_sunday', 1.0, 4.00, CAST(:sun_sched AS jsonb),
             CAST(:all_types AS jsonb), true, 9),
            ('Holiday Pricing', 'Ontario statutory holidays — national & provincial',
             'holiday', 1.0, 5.00, NULL,
             CAST(:all_types AS jsonb), true, 10)
    """).bindparams(
        peak_sched='{"periods":[{"days":[0,1,2,3,4],"start":"07:00","end":"09:00"},{"days":[0,1,2,3],"start":"16:00","end":"18:30"},{"days":[4],"start":"16:00","end":"19:00","amount":5.00}]}',
        night_sched='{"periods":[{"days":[0,1,2,3,4,5,6],"start":"21:00","end":"23:59"}]}',
        overnight_sched='{"periods":[{"days":[0,1,2,3,4,5,6],"start":"00:00","end":"04:59"}]}',
        early_sched='{"periods":[{"days":[0,1,2,3,4,5,6],"start":"05:00","end":"06:59"}]}',
        sat_sched='{"periods":[{"days":[5],"start":"00:00","end":"23:59"}]}',
        sun_sched='{"periods":[{"days":[6],"start":"00:00","end":"23:59"}]}',
        all_types='["all"]',
    ))


def _revert_surcharge_rules():
    """Revert to old migration 006 multiplier-based rules."""
    op.execute(sa.text("DELETE FROM surcharge_rules"))

    op.execute(sa.text("""
        INSERT INTO surcharge_rules
            (name, description, surcharge_type, multiplier, flat_amount,
             schedule, applies_to, is_active, sort_order)
        VALUES
            ('Peak Hours', 'Weekdays 6-9 AM & 4-7 PM', 'peak_hours', 1.40, 0,
             CAST(:peak_schedule AS jsonb), CAST(:all_types AS jsonb), true, 1),
            ('Night Surcharge', 'Daily 10 PM - 6 AM', 'night', 1.25, 0,
             CAST(:night_schedule AS jsonb), CAST(:all_types AS jsonb), true, 2),
            ('Weather - Rain', 'Active during rain advisories', 'weather_rain', 1.30, 0,
             NULL, CAST(:all_types AS jsonb), false, 3),
            ('Winter Weather', 'Active during snow/ice advisories', 'winter_weather', 1.50, 0,
             NULL, CAST(:all_types AS jsonb), false, 4),
            ('Holiday Pricing', 'Ontario statutory holidays', 'holiday', 1.60, 0,
             NULL, CAST(:all_types AS jsonb), true, 5),
            ('Early Morning', 'Daily 4-6 AM', 'early_morning', 1.15, 0,
             CAST(:early_schedule AS jsonb), CAST(:all_types AS jsonb), false, 6)
    """).bindparams(
        peak_schedule='{"periods":[{"days":[0,1,2,3,4],"start":"06:00","end":"09:00"},{"days":[0,1,2,3,4],"start":"16:00","end":"19:00"}]}',
        night_schedule='{"periods":[{"days":[0,1,2,3,4,5,6],"start":"22:00","end":"23:59"},{"days":[0,1,2,3,4,5,6],"start":"00:00","end":"06:00"}]}',
        early_schedule='{"periods":[{"days":[0,1,2,3,4,5,6],"start":"04:00","end":"06:00"}]}',
        all_types='["all"]',
    ))


# ──────────────────────────────────────────────────────────────
# DIALYSIS RATE PLANS
# ──────────────────────────────────────────────────────────────

def _seed_dialysis_rate_plans():
    """Seed 4 Milton-area dialysis rate plans."""
    op.execute(sa.text("""
        INSERT INTO dialysis_rate_plans
            (id, plan_name, origin_area, destination_area, per_trip_rate,
             monthly_package_rate, monthly_package_trips, min_trips_per_week,
             is_active, created_by)
        VALUES
            (gen_random_uuid(), 'Milton to Georgetown Dialysis', 'Milton', 'Georgetown',
             18.00, 195.00, 12, 3, true, CAST(:sys_user AS uuid)),
            (gen_random_uuid(), 'Milton to Oakville Dialysis', 'Milton', 'Oakville',
             28.00, 300.00, 12, 3, true, CAST(:sys_user AS uuid)),
            (gen_random_uuid(), 'Milton to Burlington Dialysis', 'Milton', 'Burlington',
             32.00, 345.00, 12, 3, true, CAST(:sys_user AS uuid)),
            (gen_random_uuid(), 'Milton to Mississauga Dialysis', 'Milton', 'Mississauga',
             45.00, 490.00, 12, 3, true, CAST(:sys_user AS uuid))
    """).bindparams(sys_user=SYSTEM_USER_ID))
