from __future__ import annotations
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .database import SessionLocal
from . import models
from . import schemas
from .doctors import require_profile_secret
import json

router = APIRouter(prefix="/api", tags=["Secretaries"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def error(code: str, message: str, status: int = 400):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@router.post("/secretary_login_code", response_model=schemas.SecretaryLoginResponse)
def secretary_login_code(
    request: schemas.SecretaryLoginRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    Secretary login using their 6-digit code.
    
    This endpoint allows a secretary to login using their unique 6-digit code
    and returns their profile information including clinic and doctor details.
    """
    
    try:
        # Look up secretary by their code
        secretary = db.query(models.Secretary).filter(
            models.Secretary.secretary_id == request.secretary_code
        ).first()
        
        if not secretary:
            raise HTTPException(
                status_code=404,
                detail="Secretary code not found"
            )
        
        # Generate secretary_id in format "S-{clinic_id}"
        formatted_secretary_id = f"S-{secretary.clinic_id}"

        # محاولة استخراج receiving_patients من دكتور له نفس clinic_id داخل general_info.clinic_id
        receiving_patients = None
        doctors = db.query(models.Doctor).filter(models.Doctor.profile_json.isnot(None)).all()
        trans = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
        for doc in doctors:
            raw = doc.profile_json
            if not raw:
                continue
            try:
                pobj = json.loads(raw)
            except Exception:
                continue
            if not isinstance(pobj, dict):
                continue
            gi = pobj.get("general_info", {})
            if not isinstance(gi, dict):
                continue
            cid = gi.get("clinic_id")
            # تطابق clinic_id رقماً أو نصاً
            try:
                if cid is not None and int(str(cid).translate(trans).strip()) == int(secretary.clinic_id):
                    rp = gi.get("receiving_patients") or gi.get("receivingPatients") or gi.get("receiving_patients_count")
                    if rp is not None:
                        try:
                            receiving_patients = int(str(rp).translate(trans).strip())
                        except Exception:
                            receiving_patients = None
                    break
            except Exception:
                continue

        return schemas.SecretaryLoginResponse(
            status="successfuly",
            clinic_id=secretary.clinic_id,
            secretary_id=formatted_secretary_id,
            doctor_name=secretary.doctor_name,
            secretary_name=secretary.secretary_name,
            created_date=secretary.created_date,
            receiving_patients=receiving_patients
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process secretary login: {str(e)}"
        )