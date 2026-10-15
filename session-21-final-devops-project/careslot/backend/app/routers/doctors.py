from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Doctor
from ..schemas import DoctorCreate, DoctorOut, DoctorUpdate

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


def _get_or_404(db: Session, doctor_id: int) -> Doctor:
    doctor = db.get(Doctor, doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor


@router.get("", response_model=list[DoctorOut])
def list_doctors(active_only: bool = False, db: Session = Depends(get_db)):
    query = select(Doctor).order_by(Doctor.name)
    if active_only:
        query = query.where(Doctor.active.is_(True))
    return list(db.scalars(query))


@router.get("/{doctor_id}", response_model=DoctorOut)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, doctor_id)


@router.post("", response_model=DoctorOut, status_code=status.HTTP_201_CREATED)
def create_doctor(payload: DoctorCreate, db: Session = Depends(get_db)):
    doctor = Doctor(**payload.model_dump())
    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.put("/{doctor_id}", response_model=DoctorOut)
def update_doctor(doctor_id: int, payload: DoctorUpdate, db: Session = Depends(get_db)):
    doctor = _get_or_404(db, doctor_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(doctor, key, value)
    db.commit()
    db.refresh(doctor)
    return doctor


@router.delete("/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_doctor(doctor_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, doctor_id))
    db.commit()
