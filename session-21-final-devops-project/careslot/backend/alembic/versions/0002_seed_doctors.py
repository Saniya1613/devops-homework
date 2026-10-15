"""seed the clinic's doctors so a fresh install is usable

Revision ID: 0002_seed_doctors
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_seed_doctors"
down_revision = "0001_doctors_appointments"
branch_labels = None
depends_on = None

DOCTORS = [
    {"name": "Dr. Ananya Kulkarni", "specialty": "General Physician", "room": "101"},
    {"name": "Dr. Rohan Mehta", "specialty": "Pediatrics", "room": "102"},
    {"name": "Dr. Kavya Iyer", "specialty": "Dermatology", "room": "201"},
    {"name": "Dr. Arjun Deshpande", "specialty": "Orthopedics", "room": "202"},
]


doctors = sa.table("doctors", sa.column("name", sa.String), sa.column("specialty", sa.String),
                   sa.column("room", sa.String))


def upgrade():
    op.bulk_insert(doctors, DOCTORS)


def downgrade():
    op.execute(doctors.delete().where(doctors.c.name.in_([d["name"] for d in DOCTORS])))
