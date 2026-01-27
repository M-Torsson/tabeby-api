# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


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

@router.post("/patient/register", response_model=schemas.PatientUserRegisterResponse)
def patient_register(
    payload: schemas.PatientUserRegisterRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    if payload.user_role.lower() != "patient":
        raise HTTPException(status_code=400, detail="user_role must be 'patient'")

    existing = db.query(models.UserAccount).filter(models.UserAccount.phone_number == payload.phone_number).first()
    if existing:
        return schemas.PatientUserRegisterResponse(
            message="ok",
            user_server_id=f"P-{existing.id}",
            user_role=payload.user_role
        )

    ua = models.UserAccount(
        user_uid=payload.user_uid,
        user_role="patient",
        phone_number=payload.phone_number,
        doctor_id=None
    )
    db.add(ua)
    try:
        db.commit()
        db.refresh(ua)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"database error: {e}")

    return schemas.PatientUserRegisterResponse(
        message="ok",
        user_server_id=f"P-{ua.id}",
        user_role="patient"
    )
