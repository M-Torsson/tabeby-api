from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models, schemas
from .doctors import require_profile_secret
from datetime import datetime, timezone

# حالة الحالة الإنجليزية إلى العربية (أساسية قابلة للتوسعة)
STATUS_MAP = {
    "booked": "تم الحجز",
    "served": "تمت المعاينة",
    "no_show": "لم يحضر",
    "cancelled": "ملغى",
    "in_progress": "جاري المعاينة",
}

router = APIRouter(prefix="/api", tags=["Bookings"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/create_table", response_model=schemas.BookingCreateResponse)
def create_table(payload: schemas.BookingCreateRequest, db: Session = Depends(get_db), _: None = Depends(require_profile_secret)):
    # Validate days has exactly one date key as per example
    if not isinstance(payload.days, dict) or len(payload.days) == 0:
        raise HTTPException(status_code=400, detail="days must contain at least one date key")

    # We'll handle only first provided date for response wording
    first_date = list(payload.days.keys())[0]

    # Find existing booking table for clinic
    bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == payload.clinic_id).first()
    if not bt:
        bt = models.BookingTable(
            clinic_id=payload.clinic_id,
            days_json=json.dumps(payload.days, ensure_ascii=False)
        )
        db.add(bt)
        db.commit()
        return schemas.BookingCreateResponse(
            status="تم الانشاء بنجاح",
            message=f"تم انشاء القائمة بهذا التاريخ: {first_date}"
        )

    # Merge behavior: if date exists -> return 'موجود' without modification
    existing_days = {}
    try:
        existing_days = json.loads(bt.days_json)
    except Exception:
        existing_days = {}

    if first_date in existing_days:
        return schemas.BookingCreateResponse(
            status="موجود",
            message=f"التاريخ موجود مسبقاً: {first_date}"
        )

    # Add new date(s)
    existing_days.update(payload.days)
    bt.days_json = json.dumps(existing_days, ensure_ascii=False)
    db.add(bt)
    db.commit()
    return schemas.BookingCreateResponse(
        status="تم الانشاء بنجاح",
        message=f"تم انشاء القائمة بهذا التاريخ: {first_date}"
    )


@router.post("/patient_booking", response_model=schemas.PatientBookingResponse)
def patient_booking(payload: schemas.PatientBookingRequest, db: Session = Depends(get_db), _: None = Depends(require_profile_secret)):
    """إضافة مريض إلى قائمة يوم معين داخل عيادة.

    في حال لم يُرسل booking_id سيتم توليده بالشكل: B-<clinic_id>-<yyyymmdd>-XXXX
    حيث XXXX رقم متسلسل يبدأ من 0001 لذلك التاريخ.
    """
    # إما أن يكون booking_id موجوداً (مستقبلاً لو دعمنا استرجاع) أو نحتاج clinic_id + date
    if not payload.booking_id:
        if not payload.clinic_id or not payload.date:
            raise HTTPException(status_code=400, detail="يجب إرسال clinic_id و date عند عدم وجود booking_id")
    clinic_id = payload.clinic_id if payload.clinic_id is not None else None
    date_key = payload.date if payload.date is not None else None

    # جلب جدول الحجز
    bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == clinic_id).first()
    if not bt:
        raise HTTPException(status_code=404, detail="لا يوجد جدول حجز لهذه العيادة")

    try:
        days = json.loads(bt.days_json)
    except Exception:
        days = {}

    if date_key not in days:
        raise HTTPException(status_code=404, detail="التاريخ غير موجود في هذه العيادة")

    day_obj = days[date_key]
    # التحقق من الحقول الأساسية داخل اليوم
    for fld in ["capacity_total", "capacity_used", "patients", "inline_next"]:
        if fld not in day_obj:
            raise HTTPException(status_code=400, detail=f"الحقل مفقود داخل اليوم: {fld}")

    patients_list = day_obj.get("patients", [])

    # منع تكرار نفس patient_id في نفس التاريخ
    for p in patients_list:
        if p.get("patient_id") == payload.patient_id:
            raise HTTPException(status_code=409, detail="هذا المريض محجوز مسبقاً في هذا التاريخ")

    capacity_total = int(day_obj.get("capacity_total", 0))
    capacity_used = int(day_obj.get("capacity_used", 0))
    if capacity_used >= capacity_total:
        raise HTTPException(status_code=409, detail="السعة ممتلئة لهذا اليوم")

    # حساب التسلسل (token)
    next_token = capacity_used + 1

    # توليد booking_id إن لم يُرسل
    if not payload.booking_id:
        # عدّ جميع الحجوزات لهذا التاريخ (patients_list length بعد التأكد أعلاه)
        seq = len(patients_list) + 1
        booking_id = f"B-{clinic_id}-{date_key.replace('-', '')}-{seq:04d}"
    else:
        booking_id = payload.booking_id

    # حالة الحجز (تحويل لو أُرسلت إنجليزية)
    raw_status = payload.status or "booked"
    status_ar = STATUS_MAP.get(raw_status, raw_status)

    # created_at
    created_at = payload.created_at or datetime.now(timezone.utc).isoformat()

    patient_entry = {
        "booking_id": booking_id,
        "token": next_token,
        "patient_id": payload.patient_id,
        "name": payload.name,
        "phone": payload.phone,
        "source": payload.source,
        "status": status_ar,
        "created_at": created_at,
    }
    if payload.source == "secretary_app" and payload.secretary_id:
        patient_entry["secretary_id"] = payload.secretary_id

    patients_list.append(patient_entry)

    # تحديث السعة و inline_next
    day_obj["capacity_used"] = next_token
    day_obj["inline_next"] = next_token + 1
    day_obj["patients"] = patients_list
    days[date_key] = day_obj

    # حفظ
    bt.days_json = json.dumps(days, ensure_ascii=False)
    db.add(bt)
    db.commit()

    return schemas.PatientBookingResponse(
        message=f"تم الحجز بنجاح بأسم: {payload.name}",
        booking_id=booking_id,
        token=next_token,
        capacity_used=next_token,
        capacity_total=capacity_total,
        inline_next=day_obj.get("inline_next", next_token + 1),
        status=status_ar,
    )
