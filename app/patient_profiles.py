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
        is_active=getattr(prof, 'is_active', True),  # default to True if column doesn't exist yet
        created_at=prof.created_at,
        updated_at=prof.updated_at,
    )


@router.get("/patient/profile/{user_server_id}", response_model=schemas.PatientProfileResponse)
def get_patient_profile(
    user_server_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    # allow formats: P-<id> or just <id>
    raw = user_server_id.strip()
    if raw.upper().startswith("P-"):
        raw = raw.split("-", 1)[1]
    try:
        ua_id = int(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid user_server_id format; expected P-<id> or <id>")

    ua = db.query(models.UserAccount).filter_by(id=ua_id).first()
    if not ua:
        raise HTTPException(status_code=404, detail="user_account not found")

    prof = db.query(models.PatientProfile).filter_by(user_account_id=ua.id).first()
    if not prof:
        raise HTTPException(status_code=404, detail="patient_profile not found")

    return schemas.PatientProfileResponse(
        id=prof.id,
        user_server_id=f"P-{ua.id}",
        patient_name=prof.patient_name,
        phone_number=prof.phone_number,
        gender=prof.gender,
        date_of_birth=prof.date_of_birth,
        is_active=getattr(prof, 'is_active', True),  # default to True if column doesn't exist yet
        created_at=prof.created_at,
        updated_at=prof.updated_at,
    )


@router.get("/patients/all", response_model=list[schemas.PatientProfileResponse])
def get_all_patients(
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    Get all patient profiles from the database.
    Requires Doctor-Secret authentication.
    """
    profiles = db.query(models.PatientProfile).all()
    result = []
    for prof in profiles:
        ua = db.query(models.UserAccount).filter_by(id=prof.user_account_id).first()
        if ua:
            result.append(schemas.PatientProfileResponse(
                id=prof.id,
                user_server_id=f"P-{ua.id}",
                patient_name=prof.patient_name,
                phone_number=prof.phone_number,
                gender=prof.gender,
                date_of_birth=prof.date_of_birth,
                is_active=getattr(prof, 'is_active', True),  # default to True if column doesn't exist yet
                created_at=prof.created_at,
                updated_at=prof.updated_at,
            ))
    return result


@router.get("/patients/stats/count")
def get_patients_count_stats(
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    الحصول على إحصائيات عدد المرضى حسب الحالة
    
    Returns:
        {
            "total": 200,
            "active": 180,
            "inactive": 20
        }
    """
    # العدد الكلي
    total_count = db.query(models.PatientProfile).count()
    
    # عدد المرضى النشطين (is_active = True)
    active_count = db.query(models.PatientProfile).filter(
        models.PatientProfile.is_active == True
    ).count()
    
    # عدد المرضى غير النشطين (is_active = False)
    inactive_count = db.query(models.PatientProfile).filter(
        models.PatientProfile.is_active == False
    ).count()
    
    return {
        "total": total_count,
        "active": active_count,
        "inactive": inactive_count
    }
