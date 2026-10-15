from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import Appointment, Doctor
from ..schemas import AppointmentCreate, AppointmentOut, AppointmentUpdate, DoctorLoad, StatsOut

router = APIRouter(prefix="/api/appointments", tags=["appointments"])
INACTIVE = ("CANCELLED", "NO_SHOW")


def _aware(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC so comparisons work on both PostgreSQL and SQLite."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _to_out(a: Appointment) -> AppointmentOut:
    return AppointmentOut(
        id=a.id, doctor_id=a.doctor_id, patient_name=a.patient_name, patient_phone=a.patient_phone,
        reason=a.reason, scheduled_at=_aware(a.scheduled_at), duration_minutes=a.duration_minutes,
        status=a.status, notes=a.notes, created_at=a.created_at,
        doctor_name=a.doctor.name, specialty=a.doctor.specialty,
    )


def _get_or_404(db: Session, appointment_id: int) -> Appointment:
    appt = db.get(Appointment, appointment_id, options=[joinedload(Appointment.doctor)])
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appt


def _check_slot(db: Session, doctor_id: int, start: datetime, minutes: int, ignore_id: int | None = None) -> None:
    """Business rules: the doctor must exist and be active, and must not be double-booked."""
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    if not doctor.active:
        raise HTTPException(status_code=409, detail=f"{doctor.name} is not taking appointments")
    start = _aware(start)
    end = start + timedelta(minutes=minutes)
    same_day = select(Appointment).where(
        Appointment.doctor_id == doctor_id,
        Appointment.status.not_in(INACTIVE),
        Appointment.scheduled_at >= start - timedelta(hours=4),
        Appointment.scheduled_at < end,
    )
    for other in db.scalars(same_day):
        if other.id == ignore_id:
            continue
        o_start = _aware(other.scheduled_at)
        if o_start < end and start < o_start + timedelta(minutes=other.duration_minutes):
            raise HTTPException(status_code=409,
                                detail=f"{doctor.name} is already booked for that time slot")


@router.get("", response_model=list[AppointmentOut])
def list_appointments(
    status_filter: str | None = Query(default=None, alias="status"),
    doctor_id: int | None = None,
    on: date | None = Query(default=None, description="Only appointments on this day (YYYY-MM-DD, UTC)"),
    db: Session = Depends(get_db),
):
    query = select(Appointment).options(joinedload(Appointment.doctor)).order_by(Appointment.scheduled_at)
    if status_filter:
        query = query.where(Appointment.status == status_filter.upper())
    if doctor_id:
        query = query.where(Appointment.doctor_id == doctor_id)
    if on:
        day = datetime.combine(on, time.min, tzinfo=timezone.utc)
        query = query.where(Appointment.scheduled_at >= day, Appointment.scheduled_at < day + timedelta(days=1))
    return [_to_out(a) for a in db.scalars(query)]


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Appointment.status, func.count(Appointment.id)).group_by(Appointment.status)).all())
    today = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    today_count = db.scalar(select(func.count(Appointment.id)).where(
        Appointment.scheduled_at >= today, Appointment.scheduled_at < today + timedelta(days=1))) or 0
    load_rows = db.execute(
        select(Doctor.id, Doctor.name, func.count(Appointment.id))
        .join(Appointment, Appointment.doctor_id == Doctor.id, isouter=True)
        .group_by(Doctor.id, Doctor.name).order_by(Doctor.name)
    ).all()
    return StatsOut(
        total=sum(counts.values()), today=today_count,
        scheduled=counts.get("SCHEDULED", 0), checkedIn=counts.get("CHECKED_IN", 0),
        completed=counts.get("COMPLETED", 0), cancelled=counts.get("CANCELLED", 0), noShow=counts.get("NO_SHOW", 0),
        doctors=len(load_rows),
        byDoctor=[DoctorLoad(doctor_id=i, doctor_name=n, appointments=c) for i, n, c in load_rows],
    )


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    return _to_out(_get_or_404(db, appointment_id))


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def book_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    _check_slot(db, payload.doctor_id, payload.scheduled_at, payload.duration_minutes)
    appt = Appointment(**payload.model_dump())
    db.add(appt)
    db.commit()
    return _to_out(_get_or_404(db, appt.id))


@router.put("/{appointment_id}", response_model=AppointmentOut)
def update_appointment(appointment_id: int, payload: AppointmentUpdate, db: Session = Depends(get_db)):
    appt = _get_or_404(db, appointment_id)
    changes = payload.model_dump(exclude_unset=True)
    rescheduling = {"doctor_id", "scheduled_at", "duration_minutes"} & changes.keys()
    reactivating = changes.get("status") not in (None, *INACTIVE) and appt.status in INACTIVE
    if rescheduling or reactivating:
        _check_slot(db, changes.get("doctor_id", appt.doctor_id), changes.get("scheduled_at", appt.scheduled_at),
                    changes.get("duration_minutes", appt.duration_minutes), ignore_id=appt.id)
    for key, value in changes.items():
        setattr(appt, key, value)
    db.commit()
    db.expire_all()
    return _to_out(_get_or_404(db, appointment_id))


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, appointment_id))
    db.commit()
