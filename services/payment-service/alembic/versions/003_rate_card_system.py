"""Add rate card system tables and extend fare_breakdowns.

Revision ID: 003
Revises: 002
"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

# Default rate card config for Halton Region, Ontario
DEFAULT_RATE_CARD_CONFIG = {
    "timezone": "America/Toronto",
    "base_fare": {
        "flat_rate": 12.00,
        "distance_threshold_km": 10.0,
        "per_km_beyond_threshold": 0.75,
    },
    "fees": {
        "surcharge_flat_per_trip": 0.06,
        "insurance_payment_gateway_fee": 1.50,
    },
    "wait_time": {
        "free_minutes": 10,
        "per_minute_after_free": 0.50,
    },
    "max_surcharge_cap": 18.00,
    "platform_fee_percent": 0.20,
    "weather_surcharges": {
        "light_snow": 3.00,
        "heavy_snow": 5.00,
        "post_storm": 3.00,
    },
    "rush_hour_surcharges": [
        {"name": "morning_rush", "days": [0, 1, 2, 3, 4], "start": "07:00", "end": "09:00", "amount": 4.00},
        {"name": "evening_rush", "days": [0, 1, 2, 3], "start": "16:00", "end": "18:30", "amount": 4.00},
        {"name": "friday_evening", "days": [4], "start": "16:00", "end": "19:00", "amount": 5.00},
    ],
    "time_of_day_surcharges": [
        {"name": "early_morning", "start": "05:00", "end": "06:59", "amount": 5.00},
        {"name": "late_night", "start": "21:00", "end": "23:59", "amount": 4.00},
        {"name": "overnight", "start": "00:00", "end": "04:59", "amount": 8.00},
    ],
    "weekend_surcharges": {
        "saturday": 3.00,
        "sunday": 4.00,
    },
    "holiday_surcharge": 5.00,
    "highway_407_tolls": {
        "milton_oakville": 8.00,
        "milton_brampton": 9.00,
        "milton_mississauga": 10.00,
    },
}

# System bootstrap UUID for seed data
SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # 1. Create rate_cards table
    op.create_table(
        "rate_cards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer, nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("config", JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, default=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_rate_cards_is_active", "rate_cards", ["is_active"])

    # 2. Create holidays table
    op.create_table(
        "holidays",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("date", sa.Date, nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_holidays_date", "holidays", ["date"])

    # 3. Create weather_conditions table
    op.create_table(
        "weather_conditions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("condition_type", sa.String(30), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, default=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 4. Create dialysis_rate_plans table
    op.create_table(
        "dialysis_rate_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_name", sa.String(200), nullable=False),
        sa.Column("origin_area", sa.String(100), nullable=False),
        sa.Column("destination_area", sa.String(100), nullable=False),
        sa.Column("per_trip_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("monthly_package_rate", sa.Numeric(10, 2), nullable=True),
        sa.Column("monthly_package_trips", sa.Integer, default=12),
        sa.Column("min_trips_per_week", sa.Integer, default=3),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 5. Add new columns to fare_breakdowns
    op.add_column("fare_breakdowns", sa.Column("distance_km", sa.Numeric(10, 2), nullable=True))
    op.add_column("fare_breakdowns", sa.Column("wait_time_minutes", sa.Integer, nullable=True, server_default="0"))
    op.add_column("fare_breakdowns", sa.Column("wait_time_charge", sa.Numeric(10, 2), nullable=True, server_default="0"))
    op.add_column("fare_breakdowns", sa.Column("surcharges_total", sa.Numeric(10, 2), nullable=True, server_default="0"))
    op.add_column("fare_breakdowns", sa.Column("surcharges_capped", sa.Numeric(10, 2), nullable=True, server_default="0"))
    op.add_column("fare_breakdowns", sa.Column("surcharge_details", JSONB, nullable=True))
    op.add_column("fare_breakdowns", sa.Column("highway_407_toll", sa.Numeric(10, 2), nullable=True, server_default="0"))
    op.add_column("fare_breakdowns", sa.Column("insurance_gateway_fee", sa.Numeric(10, 2), nullable=True, server_default="0"))
    op.add_column("fare_breakdowns", sa.Column("flat_surcharge", sa.Numeric(10, 2), nullable=True, server_default="0"))
    op.add_column("fare_breakdowns", sa.Column("is_dialysis_rate", sa.Boolean, nullable=True, server_default="false"))
    op.add_column("fare_breakdowns", sa.Column("dialysis_plan_id", UUID(as_uuid=True), nullable=True))
    op.add_column("fare_breakdowns", sa.Column("rate_card_version", sa.Integer, nullable=True))

    # 6. Seed default rate card
    config_json = json.dumps(DEFAULT_RATE_CARD_CONFIG)
    op.execute(
        sa.text(
            "INSERT INTO rate_cards (id, version, name, config, is_active, created_by, notes) "
            "VALUES (gen_random_uuid(), 1, :name, CAST(:config AS jsonb), true, CAST(:created_by AS uuid), :notes)"
        ).bindparams(
            name="Halton Region Default - April 2026",
            config=config_json,
            created_by=SYSTEM_USER_ID,
            notes="Initial rate card seeded by migration",
        )
    )

    # 7. Seed weather conditions
    for condition_type in ["light_snow", "heavy_snow", "post_storm"]:
        op.execute(
            sa.text(
                "INSERT INTO weather_conditions (id, condition_type, is_active) "
                "VALUES (gen_random_uuid(), :condition_type, false)"
            ).bindparams(condition_type=condition_type)
        )

    # 8. Seed Ontario 2026 statutory holidays
    holidays = [
        ("2026-01-01", "New Year's Day"),
        ("2026-02-16", "Family Day"),
        ("2026-04-03", "Good Friday"),
        ("2026-05-18", "Victoria Day"),
        ("2026-07-01", "Canada Day"),
        ("2026-08-03", "Civic Holiday"),
        ("2026-09-07", "Labour Day"),
        ("2026-10-12", "Thanksgiving"),
        ("2026-12-25", "Christmas Day"),
        ("2026-12-26", "Boxing Day"),
    ]
    for holiday_date, holiday_name in holidays:
        op.execute(
            sa.text(
                "INSERT INTO holidays (id, date, name, is_active, created_by) "
                "VALUES (gen_random_uuid(), CAST(:hdate AS date), :hname, true, CAST(:created_by AS uuid))"
            ).bindparams(
                hdate=holiday_date,
                hname=holiday_name,
                created_by=SYSTEM_USER_ID,
            )
        )


def downgrade() -> None:
    # Remove fare_breakdowns columns
    for col in [
        "rate_card_version", "dialysis_plan_id", "is_dialysis_rate",
        "flat_surcharge", "insurance_gateway_fee", "highway_407_toll",
        "surcharge_details", "surcharges_capped", "surcharges_total",
        "wait_time_charge", "wait_time_minutes", "distance_km",
    ]:
        op.drop_column("fare_breakdowns", col)

    # Drop tables
    op.drop_table("dialysis_rate_plans")
    op.drop_table("weather_conditions")
    op.drop_index("ix_holidays_date", table_name="holidays")
    op.drop_table("holidays")
    op.drop_index("ix_rate_cards_is_active", table_name="rate_cards")
    op.drop_table("rate_cards")
