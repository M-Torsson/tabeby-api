from __future__ import annotations
import json
import random
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models, schemas
from .doctors import require_profile_secret

router = APIRouter(prefix="/api", tags=["Golden Bookings"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _generate_unique_code(existing_codes: set[str]) -> str:
    """توليد كود 4 أرقام فريد غير موجود في القائمة الحالية."""
    max_attempts = 100
    for _ in range(max_attempts):
        code = f"{random.randint(1000, 9999)}"
        if code not in existing_codes:
            return code
    raise HTTPException(status_code=500, detail="Unable to generate unique code")


@router.post("/create_golden_table", response_model=schemas.GoldenTableCreateResponse)
def create_golden_table(
    payload: schemas.GoldenTableCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """إنشاء جدول Golden Book جديد أو استبدال القديم."""
    if not isinstance(payload.days, dict) or len(payload.days) == 0:
        raise HTTPException(status_code=400, detail="days must contain at least one date key")
    
    first_date = list(payload.days.keys())[0]
    
    # البحث عن جدول موجود
    gt = db.query(models.GoldenBookingTable).filter(
        models.GoldenBookingTable.clinic_id == payload.clinic_id
    ).first()
    
    if gt:
        # دمج الأيام الجديدة مع الموجودة
        try:
            existing_days = json.loads(gt.days_json) if gt.days_json else {}
        except Exception:
            existing_days = {}
        existing_days.update(payload.days)
        gt.days_json = json.dumps(existing_days, ensure_ascii=False)
        db.add(gt)
        db.commit()
    else:
        # إنشاء جدول جديد
        gt = models.GoldenBookingTable(
            clinic_id=payload.clinic_id,
            days_json=json.dumps(payload.days, ensure_ascii=False)
        )
        db.add(gt)
        db.commit()
    
    return schemas.GoldenTableCreateResponse(
        status="تم الانشاء بنجاح",
        message=f"تم انشاء القائمة بهذا التاريخ: {first_date}"
    )


@router.post("/patient_golden_booking", response_model=schemas.GoldenBookingResponse)
def patient_golden_booking(
    payload: schemas.GoldenBookingRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """حجز مريض في Golden Book مع توليد كود 4 أرقام فريد."""
    
    # البحث عن الجدول
    gt = db.query(models.GoldenBookingTable).filter(
        models.GoldenBookingTable.clinic_id == payload.clinic_id
    ).first()
    
    if not gt:
        raise HTTPException(status_code=404, detail="Golden booking table not found")
    
    try:
        days = json.loads(gt.days_json) if gt.days_json else {}
    except Exception:
        days = {}
    
    if payload.date not in days:
        raise HTTPException(status_code=404, detail=f"Date {payload.date} not found in golden table")
    
    day_obj = days[payload.date]
    if not isinstance(day_obj, dict):
        raise HTTPException(status_code=400, detail="Invalid day structure")
    
    patients = day_obj.get("patients")
    if not isinstance(patients, list):
        day_obj["patients"] = []
        patients = day_obj["patients"]
    
    capacity_total = day_obj.get("capacity_total", 0)
    capacity_used = day_obj.get("capacity_used", 0)
    
    # تحقق من السعة
    if capacity_used >= capacity_total:
        raise HTTPException(status_code=400, detail="Golden table is full")
    
    # جمع الأكواد الموجودة حالياً لليوم
    existing_codes = {p.get("code") for p in patients if isinstance(p, dict) and p.get("code")}
    
    # توليد كود فريد
    new_code = _generate_unique_code(existing_codes)
    
    # حساب التوكن التالي
    next_token = max([p.get("token", 0) for p in patients if isinstance(p, dict)], default=0) + 1
    
    # تاريخ الحجز بصيغة ISO
    date_compact = payload.date.replace("-", "")  # YYYYMMDD
    booking_id = f"G-{payload.clinic_id}-{date_compact}-{payload.patient_id}"
    
    created_at = datetime.now(timezone.utc).isoformat()
    
    patient_entry = {
        "booking_id": booking_id,
        "token": next_token,
        "patient_id": payload.patient_id,
        "name": payload.name,
        "phone": payload.phone,
        "status": "تم الحجز",
        "code": new_code,
        "created_at": created_at
    }
    
    patients.append(patient_entry)
    day_obj["patients"] = patients
    day_obj["capacity_used"] = capacity_used + 1
    
    days[payload.date] = day_obj
    gt.days_json = json.dumps(days, ensure_ascii=False)
    db.add(gt)
    db.commit()
    
    return schemas.GoldenBookingResponse(
        message=f"تم الحجز بنجاح بأسم: {payload.name}",
        code=new_code
    )


@router.get("/booking_golden_days", response_model=dict)
def get_golden_booking_days(
    clinic_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """إرجاع كل أيام Golden Book لعيادة معينة."""
    gt = db.query(models.GoldenBookingTable).filter(
        models.GoldenBookingTable.clinic_id == clinic_id
    ).first()
    
    if not gt:
        return {"clinic_id": clinic_id, "days": {}}
    
    try:
        days = json.loads(gt.days_json) if gt.days_json else {}
    except Exception:
        days = {}
    
    return {"clinic_id": clinic_id, "days": days}
