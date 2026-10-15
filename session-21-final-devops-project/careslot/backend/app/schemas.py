from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AppointmentStatus = Literal["SCHEDULED", "CHECKED_IN", "COMPLETED", "CANCELLED", "NO_SHOW"]
PHONE = r"^\+?[0-9 \-]{7,20}$"


# ---------- doctors ----------
class DoctorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    specialty: str = Field(min_length=2, max_length=80)
    room: str = Field(default="", max_length=20)
    active: bool = True


class DoctorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    specialty: str | None = Field(default=None, min_length=2, max_length=80)
    room: str | None = Field(default=None, max_length=20)
    active: bool | None = None


class DoctorOut(DoctorCreate):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- appointments ----------
class AppointmentCreate(BaseModel):
    doctor_id: int
    patient_name: str = Field(min_length=2, max_length=120)
    patient_phone: str = Field(pattern=PHONE)
    reason: str = Field(default="General consultation", max_length=200)
    scheduled_at: datetime
    duration_minutes: int = Field(default=20, ge=5, le=120)
    status: AppointmentStatus = "SCHEDULED"
    notes: str = ""


class AppointmentUpdate(BaseModel):
    doctor_id: int | None = None
    patient_name: str | None = Field(default=None, min_length=2, max_length=120)
    patient_phone: str | None = Field(default=None, pattern=PHONE)
    reason: str | None = Field(default=None, max_length=200)
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=120)
    status: AppointmentStatus | None = None
    notes: str | None = None


class AppointmentOut(AppointmentCreate):
    id: int
    doctor_name: str
    specialty: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DoctorLoad(BaseModel):
    doctor_id: int
    doctor_name: str
    appointments: int


class StatsOut(BaseModel):
    total: int
    today: int
    scheduled: int
    checkedIn: int
    completed: int
    cancelled: int
    noShow: int
    doctors: int
    byDoctor: list[DoctorLoad]
