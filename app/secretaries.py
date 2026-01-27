# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


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
        secretary = db.query(models.Secretary).filter(
            models.Secretary.secretary_id == request.secretary_code
        ).first()
        
        if not secretary:
            raise HTTPException(
                status_code=404,
                detail="Secretary code not found"
            )
        
        if hasattr(secretary, 'is_active') and not secretary.is_active:
            raise HTTPException(
                status_code=403,
                detail="Secretary account is disabled by doctor"
            )
        
        formatted_secretary_id = f"S-{secretary.clinic_id}"

        receiving_patients = None
        trans = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

        def _parse_rp_from_profile(raw: str | None) -> int | None:
            if not raw:
                return None
            try:
                pobj = json.loads(raw)
            except Exception:
                return None
            if not isinstance(pobj, dict):
                return None
            gi = pobj.get("general_info", {})
            if not isinstance(gi, dict):
                return None
            rp = gi.get("receiving_patients") or gi.get("receivingPatients") or gi.get("receiving_patients_count")
            if rp is None:
                return None
            try:
                return int(str(rp).translate(trans).strip())
            except Exception:
                return None

        doc_by_id = db.query(models.Doctor).filter(models.Doctor.id == int(secretary.clinic_id)).first()
        if doc_by_id:
            rp_val = _parse_rp_from_profile(doc_by_id.profile_json)
            if rp_val is not None:
                receiving_patients = rp_val
        
        if receiving_patients is None:
            doctors = db.query(models.Doctor).filter(models.Doctor.profile_json.isnot(None)).all()
            best = None  # (name_match: bool, updated_at_ts: float, rp: int)
            target_cid = int(secretary.clinic_id)
            sec_name_norm = (secretary.doctor_name or "").strip()
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
                try:
                    if cid is None:
                        continue
                    cid_norm = int(str(cid).translate(trans).strip())
                except Exception:
                    continue
                if cid_norm != target_cid:
                    continue
                rp_val = _parse_rp_from_profile(raw)
                if rp_val is None:
                    continue
                doc_name_norm = str(gi.get("doctor_name") or doc.name or "").strip()
                name_match = (doc_name_norm == sec_name_norm and sec_name_norm != "")
                updated_ts = (doc.updated_at.timestamp() if getattr(doc, "updated_at", None) else 0.0)
                score = (1 if name_match else 0, updated_ts)
                if best is None or score > (best[0], best[1]):
                    best = (score[0], score[1], rp_val)
            if best is not None:
                receiving_patients = best[2]

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

@router.get("/doctor/secretary/{secretary_formatted_id}")
def get_secretary_info(
    secretary_formatted_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """الحصول على معلومات السكرتير - يقبل S-{secretary_code} أو {secretary_code}"""
    
    if secretary_formatted_id.startswith("S-"):
        try:
            secretary_code = int(secretary_formatted_id.split("-")[1])
        except (IndexError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid secretary_id format")
    else:
        try:
            secretary_code = int(secretary_formatted_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid secretary_id format")
    
    secretary = db.query(models.Secretary).filter_by(secretary_id=secretary_code).first()
    
    if not secretary:
        raise HTTPException(status_code=404, detail=f"Secretary not found")
    
    formatted_id = f"S-{secretary.clinic_id}"
    
    return {
        "secretary_id": formatted_id,
        "clinic_id": secretary.clinic_id,
        "active_code": secretary.secretary_id,
        "secretary_name": secretary.secretary_name,
        "created_date": secretary.created_date,
        "secretary_status": secretary.is_active if hasattr(secretary, 'is_active') else True
    }


@router.post("/doctor/secretary/toggle-status")
def toggle_secretary_status(
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """تغيير حالة السكرتير - يقبل int أو string"""
    secretary_formatted_id = payload.get("secretary_id")
    secretary_status = payload.get("secretary_status")
    
    if not secretary_formatted_id:
        raise HTTPException(status_code=400, detail="secretary_id is required")
    
    if secretary_status is None or not isinstance(secretary_status, bool):
        raise HTTPException(status_code=400, detail="secretary_status must be true or false")
    
    if isinstance(secretary_formatted_id, int):
        secretary_code = secretary_formatted_id
    elif isinstance(secretary_formatted_id, str):
        if secretary_formatted_id.startswith("S-"):
            try:
                secretary_code = int(secretary_formatted_id.split("-")[1])
            except (IndexError, ValueError):
                raise HTTPException(status_code=400, detail="Invalid secretary_id format")
        else:
            try:
                secretary_code = int(secretary_formatted_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid secretary_id format")
    else:
        raise HTTPException(status_code=400, detail="secretary_id must be int or string")
    
    secretary = db.query(models.Secretary).filter_by(secretary_id=secretary_code).first()
    
    if not secretary:
        raise HTTPException(status_code=404, detail=f"Secretary not found")
    
    if not hasattr(secretary, 'is_active'):
        raise HTTPException(status_code=500, detail="is_active column not found. Please run migration.")
    
    secretary.is_active = secretary_status
    db.commit()
    db.refresh(secretary)
    
    action = "تفعيل" if secretary_status else "تعطيل"
    
    return {
        "message": f"تم {action} السكرتير بنجاح",
        "secretary_id": secretary.secretary_id,
        "clinic_id": secretary.clinic_id,
        "secretary_status": secretary.is_active
    }
