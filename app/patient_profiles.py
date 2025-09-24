from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models, schemas
from .doctors import require_profile_secret

router = APIRouter(prefix="/api", tags=["Patients"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/patient/profile", response_model=schemas.PatientProfileResponse)
def create_or_update_patient_profile(
    payload: schemas.PatientProfileCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    # parse user_server_id in format P-<int>
    if not payload.user_server_id or not payload.user_server_id.startswith("P-"):
        raise HTTPException(status_code=400, detail="user_server_id must be like P-<id>")
    try:
        ua_id = int(payload.user_server_id.split("-", 1)[1])
    except Exception:
        raise HTTPException(status_code=400, detail="invalid user_server_id format")

    ua = db.query(models.UserAccount).filter_by(id=ua_id).first()
    if not ua:
        raise HTTPException(status_code=404, detail="user_account not found")

    # upsert profile for this user_account
    prof = db.query(models.PatientProfile).filter_by(user_account_id=ua.id).first()
    if prof:
        prof.patient_name = payload.patient_name
        prof.phone_number = payload.phone_number
        prof.gender = payload.gender
        prof.date_of_birth = payload.date_of_birth
        db.add(prof)
        db.commit()
        db.refresh(prof)
    else:
        prof = models.PatientProfile(
            user_account_id=ua.id,
            patient_name=payload.patient_name,
            phone_number=payload.phone_number,
            gender=payload.gender,
            date_of_birth=payload.date_of_birth,
        )
        db.add(prof)
        db.commit()
        db.refresh(prof)

    return schemas.PatientProfileResponse(
        id=prof.id,
        user_server_id=f"P-{ua.id}",
        patient_name=prof.patient_name,
        phone_number=prof.phone_number,
        gender=prof.gender,
        date_of_birth=prof.date_of_birth,
        created_at=prof.created_at,
        updated_at=prof.updated_at,
    )
