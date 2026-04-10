"""cities and service areas

Revision ID: 002
Revises: 001
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Create cities table ---
    op.create_table(
        "cities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("province", sa.String(50), nullable=False),
        sa.Column("number_of_zones", sa.Integer(), server_default="1"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # Create index on name for search
    op.create_index("ix_cities_name_lower", "cities", [sa.text("lower(name)")])

    # Seed initial cities (Ontario major cities)
    op.execute(
        sa.text(
            """
        INSERT INTO cities (id, name, province, number_of_zones, is_active, created_at)
        VALUES
            (gen_random_uuid(), :name1, :province, 4, true, now()),
            (gen_random_uuid(), :name2, :province, 3, true, now()),
            (gen_random_uuid(), :name3, :province, 2, true, now()),
            (gen_random_uuid(), :name4, :province, 2, true, now()),
            (gen_random_uuid(), :name5, :province, 2, true, now()),
            (gen_random_uuid(), :name6, :province, 1, true, now()),
            (gen_random_uuid(), :name7, :province, 1, true, now()),
            (gen_random_uuid(), :name8, :province, 1, true, now())
        """
        ).bindparams(
            name1="Toronto",
            name2="Ottawa",
            name3="Mississauga",
            name4="Hamilton",
            name5="London",
            name6="Markham",
            name7="Vaughan",
            name8="Kitchener",
            province="Ontario",
        )
    )


def downgrade() -> None:
    op.drop_index("ix_cities_name_lower", table_name="cities")
    op.drop_table("cities")
