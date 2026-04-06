"""pricing management tables

Revision ID: 006
Revises: 005
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Sequence for pricing change log numbers
    op.execute(sa.text("CREATE SEQUENCE IF NOT EXISTS pricing_log_seq START WITH 10"))

    # 1. service_type_configs
    op.create_table(
        "service_type_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("service_type", sa.String(30), nullable=False, unique=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("config", JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0")),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 2. surcharge_rules
    op.create_table(
        "surcharge_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("surcharge_type", sa.String(30), nullable=False),
        sa.Column("multiplier", sa.Numeric(4, 2), nullable=False, server_default=sa.text("1.0")),
        sa.Column("flat_amount", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("schedule", JSONB, nullable=True),
        sa.Column("applies_to", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0")),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 3. ride_packages
    op.create_table(
        "ride_packages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("package_type", sa.String(30), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("ride_count", sa.Integer(), nullable=True),
        sa.Column("is_unlimited", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("validity_days", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("active_subscribers", sa.Integer(), server_default=sa.text("0")),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0")),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 4. commission_configs
    op.create_table(
        "commission_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("platform_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("driver_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("fleet_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("caregiver_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("reserve_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), index=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 5. cancellation_policies
    op.create_table(
        "cancellation_policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("service_type", sa.String(30), nullable=False),
        sa.Column("cancellation_window", sa.String(30), nullable=False),
        sa.Column("fee", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("who_receives", sa.String(100), nullable=False, server_default=sa.text("'none'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 6. pricing_change_logs
    op.create_table(
        "pricing_change_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("log_number", sa.Integer(), nullable=False),
        sa.Column("admin_id", UUID(as_uuid=True), nullable=False),
        sa.Column("admin_name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("change_description", sa.String(500), nullable=False),
        sa.Column("before_value", sa.String(200), nullable=True),
        sa.Column("after_value", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Seed Data ──

    # Service Type Configs
    op.execute(sa.text("""
        INSERT INTO service_type_configs (service_type, display_name, config, sort_order) VALUES
        ('standard', 'Standard Vehicle', CAST(:standard_config AS jsonb), 1),
        ('wheelchair_wav', 'Wheelchair (WAV)', CAST(:wav_config AS jsonb), 2),
        ('stretcher', 'Stretcher Transport', CAST(:stretcher_config AS jsonb), 3),
        ('psw_caregiver', 'PSW / Caregiver', CAST(:psw_config AS jsonb), 4),
        ('hospital_discharge', 'Hospital Discharge', CAST(:discharge_config AS jsonb), 5)
    """).bindparams(
        standard_config='{"rate_components":{"base_fare":12.00,"per_km_rate":2.20,"booking_fee":3.50,"wait_time_per_min":0.45,"minimum_fare":15.00},"distance_rules":{"short_trip_km":5,"medium_trip_km":25,"long_trip_km":50},"route_pricing":{"toronto_to_hamilton":{"distance_km":70,"estimated_fare":166.50},"toronto_to_mississauga":{"distance_km":30,"estimated_fare":78.50},"toronto_to_brampton":{"distance_km":40,"estimated_fare":100.50},"toronto_to_markham":{"distance_km":32,"estimated_fare":82.90},"toronto_to_scarborough":{"distance_km":20,"estimated_fare":56.50},"hamilton_to_burlington":{"distance_km":15,"estimated_fare":45.50},"ottawa_to_gatineau":{"distance_km":12,"estimated_fare":38.90}},"toll_charges":{"highway_407":{"per_km":0.25,"minimum":2.50}},"dialysis_discounts":{"discount_percent":15,"max_discount":25.00}}',
        wav_config='{"rate_components":{"base_fare":22.00,"per_km_rate":2.80,"accessibility_fee":15.00,"booking_fee":3.50,"wait_time_per_min":0.55,"minimum_fare":45.00},"platform_commission":0.18,"vendor_terms":{"cancellation_window_hours":24,"late_cancellation_fee":35.00,"no_show_fee":45.00},"route_pricing":{"toronto_to_hamilton":{"distance_km":70,"estimated_fare":234.50},"toronto_to_mississauga":{"distance_km":30,"estimated_fare":124.50},"toronto_to_brampton":{"distance_km":40,"estimated_fare":152.50}}}',
        stretcher_config='{"rate_components":{"base_fare":85.00,"per_km_rate":4.50,"attendant_fee":35.00,"equipment_fee":25.00,"booking_fee":5.00,"wait_time_per_min":0.75,"minimum_fare":150.00},"revenue_split":{"platform":0.18,"transport_company":0.82},"partnership_terms":{"insurance_required":true,"min_vehicles":2,"certification":"Ontario Stretcher Transport License"}}',
        psw_config='{"service_rates":{"hourly_rate":32.00,"half_day_rate":120.00,"full_day_rate":220.00,"overnight_rate":180.00,"weekend_premium":1.25},"terms":{"minimum_booking_hours":2,"cancellation_window_hours":12,"late_cancellation_fee":25.00}}',
        discharge_config='{"package_overview":{"base_price":89.00,"includes":"Transport + 1hr wait + wheelchair assist"},"components":{"transport_base":55.00,"wait_time_included_min":60,"additional_wait_per_min":0.50,"wheelchair_assist":15.00,"medication_pickup":19.00,"pharmacy_stop":12.00}}'
    ))

    # Surcharge Rules
    op.execute(sa.text("""
        INSERT INTO surcharge_rules (name, description, surcharge_type, multiplier, flat_amount, schedule, applies_to, is_active, sort_order) VALUES
        ('Peak Hours', 'Weekdays 6-9 AM & 4-7 PM', 'peak_hours', 1.40, 0, CAST(:peak_schedule AS jsonb), CAST(:all_types AS jsonb), true, 1),
        ('Night Surcharge', 'Daily 10 PM - 6 AM', 'night', 1.25, 0, CAST(:night_schedule AS jsonb), CAST(:all_types AS jsonb), true, 2),
        ('Weather - Rain', 'Active during rain advisories', 'weather_rain', 1.30, 0, NULL, CAST(:all_types AS jsonb), false, 3),
        ('Winter Weather', 'Active during snow/ice advisories', 'winter_weather', 1.50, 0, NULL, CAST(:all_types AS jsonb), false, 4),
        ('Holiday Pricing', 'Ontario statutory holidays', 'holiday', 1.60, 0, NULL, CAST(:all_types AS jsonb), true, 5),
        ('Early Morning', 'Daily 4-6 AM', 'early_morning', 1.15, 0, CAST(:early_schedule AS jsonb), CAST(:all_types AS jsonb), false, 6)
    """).bindparams(
        peak_schedule='{"periods":[{"days":[0,1,2,3,4],"start":"06:00","end":"09:00"},{"days":[0,1,2,3,4],"start":"16:00","end":"19:00"}]}',
        night_schedule='{"periods":[{"days":[0,1,2,3,4,5,6],"start":"22:00","end":"23:59"},{"days":[0,1,2,3,4,5,6],"start":"00:00","end":"06:00"}]}',
        early_schedule='{"periods":[{"days":[0,1,2,3,4,5,6],"start":"04:00","end":"06:00"}]}',
        all_types='["all"]'
    ))

    # Ride Packages
    op.execute(sa.text("""
        INSERT INTO ride_packages (name, description, package_type, price, ride_count, is_unlimited, discount_percent, validity_days, sort_order) VALUES
        ('10-Ride Bundle', 'Save 7% on 10 rides. Perfect for regular appointments.', 'rider', 79.00, 10, false, 7.00, 60, 1),
        ('20-Ride Bundle', 'Save 14% on 20 rides. Great value for frequent riders.', 'rider', 145.00, 20, false, 14.00, 90, 2),
        ('Monthly Unlimited', 'Unlimited rides for 30 days. Best for daily commuters.', 'subscription', 189.00, NULL, true, 20.00, 30, 3),
        ('Corporate Plan - 50', '50 rides for your organization. Volume discount included.', 'corporate', 340.00, 50, false, 20.00, 120, 4),
        ('Corporate Plan - 100', '100 rides for larger organizations. Maximum savings.', 'corporate', 620.00, 100, false, 27.00, 180, 5),
        ('Community Access', 'Subsidized rides for community health programs.', 'rider', 29.00, 10, false, 45.00, 90, 6),
        ('Medical VIP Monthly', 'Priority unlimited rides with premium support.', 'subscription', 249.00, NULL, true, 15.00, 30, 7)
    """))

    # Commission Config v1
    op.execute(sa.text("""
        INSERT INTO commission_configs (platform_percent, driver_percent, fleet_percent, caregiver_percent, reserve_percent, is_active, version) VALUES
        (18.00, 47.00, 20.00, 10.00, 5.00, true, 1)
    """))

    # Cancellation Policies (3 service types x 5 windows)
    op.execute(sa.text("""
        INSERT INTO cancellation_policies (service_type, cancellation_window, fee, who_receives, notes, sort_order) VALUES
        ('ambulatory', '24_hours_plus', 0, 'none', 'Full refund, no fee charged', 1),
        ('ambulatory', '2_24_hours', 15.00, 'medigo_platform', 'Administrative fee only', 2),
        ('ambulatory', 'under_2_hours', 25.00, 'driver_80_medigo_20', 'Driver receives 80% ($20), MediGo receives 20% ($5)', 3),
        ('ambulatory', 'after_dispatch', 35.00, 'driver_80_medigo_20', 'Driver receives 80% ($28), MediGo receives 20% ($7)', 4),
        ('ambulatory', 'no_show', 45.00, 'driver_85_medigo_15', 'Driver receives 85% ($38.25), MediGo receives 15% ($6.75)', 5),
        ('wheelchair_wav', '24_hours_plus', 0, 'none', 'Full refund, no fee charged', 6),
        ('wheelchair_wav', '2_24_hours', 25.00, 'medigo_platform', 'Higher admin fee due to specialized vehicle', 7),
        ('wheelchair_wav', 'under_2_hours', 45.00, 'driver_70_vendor_20_medigo_10', 'Split: Driver 70%, WAV vendor 20%, MediGo 10%', 8),
        ('wheelchair_wav', 'after_dispatch', 65.00, 'driver_70_vendor_20_medigo_10', 'Split: Driver 70%, WAV vendor 20%, MediGo 10%', 9),
        ('wheelchair_wav', 'no_show', 85.00, 'driver_70_vendor_25_medigo_5', 'Split: Driver 70%, WAV vendor 25%, MediGo 5%', 10),
        ('stretcher', '24_hours_plus', 0, 'none', 'Full refund, no fee charged', 11),
        ('stretcher', '2_24_hours', 50.00, 'medigo_platform', 'Higher admin fee due to crew + equipment', 12),
        ('stretcher', 'under_2_hours', 85.00, 'company_75_medigo_25', 'Transport company receives 75%, MediGo 25%', 13),
        ('stretcher', 'after_dispatch', 120.00, 'company_80_medigo_20', 'Transport company receives 80%, MediGo 20%', 14),
        ('stretcher', 'no_show', 150.00, 'company_85_medigo_15', 'Transport company receives 85%, MediGo 15%', 15)
    """))


def downgrade() -> None:
    op.drop_table("pricing_change_logs")
    op.drop_table("cancellation_policies")
    op.drop_table("commission_configs")
    op.drop_table("ride_packages")
    op.drop_table("surcharge_rules")
    op.drop_table("service_type_configs")
    op.execute(sa.text("DROP SEQUENCE IF EXISTS pricing_log_seq"))
