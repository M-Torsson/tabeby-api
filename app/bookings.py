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

    # Normalize: remove inline_next keys if provided by client (لم نعد نستخدمه)
    cleaned_days = {}
    for d, obj in payload.days.items():
        if isinstance(obj, dict) and "inline_next" in obj:
            obj = {k: v for k, v in obj.items() if k != "inline_next"}
        cleaned_days[d] = obj

    # Find existing booking table for clinic
    bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == payload.clinic_id).first()
    if not bt:
        bt = models.BookingTable(
            clinic_id=payload.clinic_id,
            days_json=json.dumps(cleaned_days, ensure_ascii=False)
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
    # Merge new day(s) after stripping inline_next
    existing_days.update(cleaned_days)
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
    # إما أن يكون booking_id موجوداً أو نحتاج clinic_id + date لتوليده
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
    for fld in ["capacity_total", "capacity_used", "patients"]:
        if fld not in day_obj:
            raise HTTPException(status_code=400, detail=f"الحقل مفقود داخل اليوم: {fld}")

    patients_list = day_obj.get("patients", [])

    # توليد patient_id تلقائياً إذا لم يُرسل: صيغة P-<number> تبدأ من 101 حسب أعلى رقم سابق عبر جميع الأيام للعيادة
    if not payload.patient_id:
        max_num = 100  # سيصبح 101 عند عدم وجود أي مريض
        # فحص كل الأيام لاستخراج أقصى رقم patient_id
        for d_obj in days.values():
            for p in d_obj.get("patients", []):
                pid = p.get("patient_id")
                if pid and pid.startswith("P-"):
                    try:
                        num = int(pid.split("-",1)[1])
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        pass
        new_num = max_num + 1
        payload.patient_id = f"P-{new_num}"

    # منع تكرار نفس patient_id في نفس التاريخ (بعد التوليد)
    for p in patients_list:
        if p.get("patient_id") == payload.patient_id:
            raise HTTPException(status_code=409, detail="هذا المريض محجوز مسبقاً في هذا التاريخ")

    capacity_total = int(day_obj.get("capacity_total", 0))
    capacity_used = int(day_obj.get("capacity_used", 0))
    if capacity_used >= capacity_total:
        raise HTTPException(status_code=409, detail="السعة ممتلئة لهذا اليوم")

    # حساب التسلسل (token)
    next_token = capacity_used + 1

    # توليد booking_id إن لم يُرسل مع نمطين:
    # secretary_app: S-<clinic_id>-<YYYYMMDD>-NNN (3 أرقام)
    # patient_app: B-<clinic_id>-<YYYYMMDD>-NNNN (4 أرقام كما السابق)
    if not payload.booking_id:
        seq = len(patients_list) + 1
        date_compact = date_key.replace('-', '')
        if payload.source == "secretary_app":
            booking_id = f"S-{clinic_id}-{date_compact}-{seq:03d}"
        else:
            booking_id = f"B-{clinic_id}-{date_compact}-{seq:04d}"
    else:
        booking_id = payload.booking_id
        # التحقق من صحة النمط إذا أُرسل
        date_compact = date_key.replace('-', '') if date_key else ''
        if payload.source == "secretary_app":
            # يجب أن يبدأ بـ S-<clinic_id>-<date>- و آخر جزء 3 أرقام
            expected_prefix = f"S-{clinic_id}-{date_compact}-"
            if not booking_id.startswith(expected_prefix):
                raise HTTPException(status_code=400, detail="booking_id غير متوافق مع النمط المطلوب للسكرتير")
        else:
            expected_prefix = f"B-{clinic_id}-{date_compact}-"
            if not booking_id.startswith(expected_prefix):
                raise HTTPException(status_code=400, detail="booking_id غير متوافق مع النمط المطلوب للتطبيق")

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
        "clinic_id": clinic_id,
        "date": date_key,
    }
    if payload.source == "secretary_app" and payload.secretary_id:
        patient_entry["secretary_id"] = payload.secretary_id

    patients_list.append(patient_entry)

    # تحديث السعة (لم نعد نستعمل inline_next)
    day_obj["capacity_used"] = next_token
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
        status=status_ar,
        clinic_id=clinic_id,
        date=date_key,
    )


@router.post("/add_day", response_model=schemas.AddDayResponse)
def add_day(payload: schemas.AddDayRequest, db: Session = Depends(get_db), _: None = Depends(require_profile_secret)):
    """إضافة يوم جديد (التالي) تلقائياً بعد آخر يوم موجود لنفس العيادة.

    الشروط:
    - يجب أن يوجد جدول حجز للعيادة.
    - نحدد آخر تاريخ (max) موجود.
    - لا نضيف يوم جديد إلا إذا كان اليوم الأخير ممتلئاً (capacity_used == capacity_total).
    - تاريخ اليوم الجديد = اليوم الأخير + 1 يوم (بنفس تنسيق YYYY-MM-DD).
    - السعة: إن أرسل capacity_total نستخدمها، وإلا ننسخ من آخر يوم.
    - status: إن أرسل نستخدمه وإلا 'open'.
    - نمنع التكرار إذا التاريخ الجديد موجود (حماية سباق).
    """
    bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == payload.clinic_id).first()
    if not bt:
        raise HTTPException(status_code=404, detail="لا يوجد جدول حجز لهذه العيادة")

    try:
        days = json.loads(bt.days_json) if bt.days_json else {}
    except Exception:
        days = {}

    if not days:
        raise HTTPException(status_code=400, detail="لا توجد تواريخ حالياً، استخدم create_table أولاً")

    # الحصول على آخر تاريخ (مفترض صيغة YYYY-MM-DD) بترتيب معجمي كافٍ لهذه الصيغة
    try:
        last_date = max(days.keys())
    except ValueError:
        raise HTTPException(status_code=400, detail="فشل في تحديد آخر تاريخ")

    last_day = days.get(last_date, {})
    if not all(k in last_day for k in ["capacity_total", "capacity_used", "patients"]):
        raise HTTPException(status_code=400, detail="اليوم الأخير غير مكتمل البيانات")

    capacity_total_last = int(last_day.get("capacity_total", 0))
    capacity_used_last = int(last_day.get("capacity_used", 0))

    if capacity_total_last <= 0:
        raise HTTPException(status_code=400, detail="القيمة capacity_total لليوم الأخير غير صالحة")

    if capacity_used_last < capacity_total_last:
        # غير ممتلئ بعد
        return schemas.AddDayResponse(
            status="مرفوض",
            message=f"اليوم الأخير {last_date} غير ممتلئ بعد ({capacity_used_last}/{capacity_total_last})",
            date_added=None
        )

    # حساب التاريخ الجديد
    try:
        last_dt = datetime.strptime(last_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="تنسيق التاريخ الأخير غير صحيح")

    from datetime import timedelta
    new_dt = last_dt + timedelta(days=1)
    new_date_str = new_dt.strftime("%Y-%m-%d")

    if new_date_str in days:
        # سباق أو موجود
        return schemas.AddDayResponse(
            status="موجود",
            message=f"التاريخ الجديد موجود مسبقاً: {new_date_str}",
            date_added=new_date_str
        )

    new_capacity_total = payload.capacity_total if payload.capacity_total is not None else capacity_total_last
    if new_capacity_total <= 0:
        raise HTTPException(status_code=400, detail="capacity_total الجديد غير صالح")

    new_status = payload.status or "open"

    # بناء اليوم الجديد
    new_day_obj = {
        "source": "patient_app",  # ثابت حسب التوافق الحالي
        "status": new_status,
        "capacity_total": new_capacity_total,
        "capacity_used": 0,
        "patients": []
    }
    days[new_date_str] = new_day_obj

    bt.days_json = json.dumps(days, ensure_ascii=False)
    db.add(bt)
    db.commit()

    return schemas.AddDayResponse(
        status="تم الانشاء بنجاح",
        message=f"تمت إضافة اليوم الجديد: {new_date_str}",
        date_added=new_date_str
    )


@router.get("/booking_days", response_model=schemas.BookingDaysFullResponse)
def get_booking_days(clinic_id: int, db: Session = Depends(get_db), _: None = Depends(require_profile_secret)):
    """إرجاع كل الأيام (days_json) المخزنة لعيادة محددة.

    استعلام بسيط يعتمد على clinic_id.
    يعيد نفس البنية المخزنة بدون تعديل.
    """
    bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == clinic_id).first()
    if not bt:
        raise HTTPException(status_code=404, detail="لا يوجد جدول حجز لهذه العيادة")
    try:
        days = json.loads(bt.days_json) if bt.days_json else {}
    except Exception:
        days = {}
    return schemas.BookingDaysFullResponse(clinic_id=clinic_id, days=days)
