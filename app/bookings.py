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

    # Helper: derive capacity_total from doctor profile if missing
    def _derive_capacity_total(clinic_id: int) -> int | None:
        # scan doctors with profile_json and match clinic_id inside general_info.clinic_id
        doctors = db.query(models.Doctor).filter(models.Doctor.profile_json.isnot(None)).all()
        trans = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
        for doc in doctors:
            try:
                pobj = json.loads(doc.profile_json) if doc.profile_json else None
            except Exception:
                pobj = None
            if not isinstance(pobj, dict):
                continue
            g = pobj.get("general_info")
            if not isinstance(g, dict):
                continue
            cid = g.get("clinic_id")
            if cid is None:
                # allow matching by provided clinic_id equals doctor id? (skip) – strict clinic_id only
                continue
            # normalize both to string for comparison
            if str(cid).strip() != str(payload.clinic_id).strip():
                continue
            raw_recv = g.get("receiving_patients") or g.get("receivingPatients") or g.get("receiving_patients_count")
            if raw_recv is None:
                return None
            try:
                num = int(str(raw_recv).translate(trans).strip())
                if num > 0:
                    return num
            except Exception:
                return None
        return None

    # Before persisting, inject capacity_total if absent in provided structure
    first_day_obj = cleaned_days.get(first_date, {}) if isinstance(cleaned_days.get(first_date), dict) else {}
    cap_present = isinstance(first_day_obj, dict) and "capacity_total" in first_day_obj
    derived_capacity: int | None = None
    if not cap_present:
        derived_capacity = _derive_capacity_total(payload.clinic_id)
        if derived_capacity is not None:
            # set defaults for required fields if not present
            first_day_obj.setdefault("source", "patient_app")
            first_day_obj.setdefault("status", "open")
            first_day_obj["capacity_total"] = derived_capacity
            first_day_obj.setdefault("capacity_used", 0)
            first_day_obj.setdefault("patients", [])
            cleaned_days[first_date] = first_day_obj
        else:
            # validate user actually provided capacity_total in this case
            raise HTTPException(status_code=400, detail="لم يتم إرسال capacity_total ولا يمكن استنتاجه من بروفايل الدكتور (receiving_patients)")

    # Find existing booking table for clinic
    bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == payload.clinic_id).first()
    if not bt:
        bt = models.BookingTable(
            clinic_id=payload.clinic_id,
            days_json=json.dumps(cleaned_days, ensure_ascii=False)
        )
        db.add(bt)
        db.commit()
        # capacity for response: prefer provided, else derived
        resp_cap = first_day_obj.get("capacity_total") if isinstance(first_day_obj, dict) else None
        return schemas.BookingCreateResponse(
            status="تم الانشاء بنجاح",
            message=f"تم انشاء القائمة بهذا التاريخ: {first_date}",
            capacity_total=resp_cap
        )

    # Merge behavior: if date exists -> return 'موجود' without modification
    existing_days = {}
    try:
        existing_days = json.loads(bt.days_json)
    except Exception:
        existing_days = {}

    if first_date in existing_days:
        # Return existing capacity_total for that date in response
        existing_cap = None
        try:
            if isinstance(existing_days.get(first_date), dict):
                existing_cap = existing_days[first_date].get("capacity_total")
        except Exception:
            existing_cap = None
        return schemas.BookingCreateResponse(
            status="موجود",
            message=f"التاريخ موجود مسبقاً: {first_date}",
            capacity_total=existing_cap
        )

    # Add new date(s)
    # Merge new day(s) after stripping inline_next
    existing_days.update(cleaned_days)
    bt.days_json = json.dumps(existing_days, ensure_ascii=False)
    db.add(bt)
    db.commit()
    # Determine capacity_total for response (from merged new day)
    merged_cap = None
    try:
        if isinstance(cleaned_days.get(first_date), dict):
            merged_cap = cleaned_days[first_date].get("capacity_total")
        elif isinstance(existing_days.get(first_date), dict):
            merged_cap = existing_days[first_date].get("capacity_total")
    except Exception:
        merged_cap = None
    return schemas.BookingCreateResponse(
        status="تم الانشاء بنجاح",
        message=f"تم انشاء القائمة بهذا التاريخ: {first_date}",
        capacity_total=merged_cap
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

    # توليد patient_id
    # - للحجز من تطبيق المريض: النظام السابق P-<number> (تسلسل عالمي للعيادة يبدأ من 101)
    # - للحجز من السكرتير: نستخدم آخر 3 أرقام من booking_id (بعد توليده) ونخزنه كقيمة مجردة مثل "003"
    auto_patient_id_for_patient_app: str | None = None
    if not payload.patient_id:
        # حساب التسلسل العام (للتطبيق فقط)
        max_num = 100  # سيصبح 101 عند عدم وجود أي مريض من التطبيق
        for d_obj in days.values():
            for p in d_obj.get("patients", []):
                pid = p.get("patient_id")
                if not pid:
                    continue
                if pid.startswith("P-"):
                    try:
                        num = int(pid.split("-", 1)[1])
                        if num > max_num:
                            max_num = num
                    except Exception:
                        pass
        auto_patient_id_for_patient_app = f"P-{max_num+1}"
        # سنقرر لاحقاً بعد توليد booking_id أيهما نستخدم حسب المصدر

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

    # الآن نحدد patient_id النهائي:
    if payload.source == "secretary_app":
        # سيُحدد بعد توليد booking_id: نأخذ آخر 3 أرقام
        pass
    else:
        if not payload.patient_id:
            payload.patient_id = auto_patient_id_for_patient_app

    # حالة الحجز (تحويل لو أُرسلت إنجليزية)
    raw_status = payload.status or "booked"
    status_ar = STATUS_MAP.get(raw_status, raw_status)

    # created_at
    created_at = payload.created_at or datetime.now(timezone.utc).isoformat()

    # لو الحجز سكرتير ولم يُرسل patient_id: خذه من آخر 3 أرقام في booking_id
    if payload.source == "secretary_app" and (not payload.patient_id):
        # booking_id الآن موجود
        suffix = booking_id.split('-')[-1]
        # تأكد أنه 3 أرقام
        if len(suffix) == 3 and suffix.isdigit():
            payload.patient_id = suffix
        else:
            # fallback احتياطي: استخدم التسلسل العام
            payload.patient_id = auto_patient_id_for_patient_app or "P-101"

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
        patient_id=payload.patient_id,
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

    # إذا أُرسل تاريخ مخصص نستخدمه مباشرة (نتجاهل شرط الامتلاء)
    custom_date = getattr(payload, "date", None)
    if custom_date:
        # تحقق من الصيغة
        try:
            datetime.strptime(custom_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="صيغة التاريخ غير صحيحة (يجب YYYY-MM-DD)")
        if custom_date in days:
            return schemas.AddDayResponse(
                status="موجود",
                message=f"التاريخ موجود مسبقاً: {custom_date}",
                date_added=custom_date
            )
        # نحتاج مرجع لسعة سابقة (إن لم يُرسل capacity_total) نأخذها من آخر يوم موجود إن وجد
        ref_capacity = None
        if days:
            try:
                last_ref = max(days.keys())
                ref_day = days.get(last_ref, {}) if isinstance(days.get(last_ref), dict) else {}
                ref_capacity = ref_day.get("capacity_total")
            except Exception:
                ref_capacity = None
        new_capacity_total = payload.capacity_total if payload.capacity_total is not None else (ref_capacity or 0)
        if new_capacity_total <= 0:
            raise HTTPException(status_code=400, detail="capacity_total غير صالح")
        new_status = payload.status or "open"
        new_day_obj = {
            "source": "patient_app",
            "status": new_status,
            "capacity_total": new_capacity_total,
            "capacity_used": 0,
            "patients": []
        }
        days[custom_date] = new_day_obj
        bt.days_json = json.dumps(days, ensure_ascii=False)
        db.add(bt)
        db.commit()
        return schemas.AddDayResponse(
            status="تم الانشاء بنجاح",
            message=f"تمت إضافة اليوم الجديد: {custom_date}",
            date_added=custom_date
        )

    # الوضع القديم (بدون تاريخ مخصص): يجب أن يوجد تواريخ سابقة
    if not days:
        raise HTTPException(status_code=400, detail="لا توجد تواريخ حالياً، استخدم create_table أولاً أو أرسل تاريخاً مخصصاً")

    # الحصول على آخر تاريخ
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

    if capacity_used_last < capacity_total_last and not getattr(payload, "force_add", False):
        return schemas.AddDayResponse(
            status="مرفوض",
            message=f"اليوم الأخير {last_date} غير ممتلئ بعد ({capacity_used_last}/{capacity_total_last})",
            date_added=None
        )

    # حساب التاريخ التالي
    try:
        last_dt = datetime.strptime(last_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="تنسيق التاريخ الأخير غير صحيح")

    from datetime import timedelta
    new_dt = last_dt + timedelta(days=1)
    new_date_str = new_dt.strftime("%Y-%m-%d")

    if new_date_str in days:
        return schemas.AddDayResponse(
            status="موجود",
            message=f"التاريخ الجديد موجود مسبقاً: {new_date_str}",
            date_added=new_date_str
        )

    new_capacity_total = payload.capacity_total if payload.capacity_total is not None else capacity_total_last
    if new_capacity_total <= 0:
        raise HTTPException(status_code=400, detail="capacity_total الجديد غير صالح")

    new_status = payload.status or "open"
    new_day_obj = {
        "source": "patient_app",
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

    # 1) إزالة الحقول القديمة inline_next إن وجدت
    # 2) تنظيف أي مفاتيح clinic_id / date داخل كل مريض
    # 3) ترتيب التواريخ تصاعدياً قبل الإرجاع
    cleaned_days = {}
    for d_key in sorted(days.keys()):  # الترتيب التصاعدي YYYY-MM-DD
        d_val = days.get(d_key)
        if not isinstance(d_val, dict):
            cleaned_days[d_key] = d_val
            continue
        # إزالة inline_next إن وجد
        if "inline_next" in d_val:
            d_val = {k: v for k, v in d_val.items() if k != "inline_next"}
        # تنظيف المرضى
        patients = d_val.get("patients")
        if isinstance(patients, list):
            new_list = []
            for p in patients:
                if isinstance(p, dict):
                    if "clinic_id" in p or "date" in p:
                        p = {k: v for k, v in p.items() if k not in ("clinic_id", "date")}
                new_list.append(p)
            d_val["patients"] = new_list
        cleaned_days[d_key] = d_val

    return schemas.BookingDaysFullResponse(clinic_id=clinic_id, days=cleaned_days)


@router.post("/edit_patient_booking", response_model=schemas.EditPatientBookingResponse)
def edit_patient_booking(payload: schemas.EditPatientBookingRequest, db: Session = Depends(get_db), _: None = Depends(require_profile_secret)):
    """تعديل (فقط) حالة مريض محدد داخل يوم ما.

    المدخلات:
      - clinic_id (إلزامي)
      - booking_id (مفضل) أو patient_id كبديل ثانوي
      - status (قد تكون إنجليزية أو عربية)

    المنطق:
      - قراءة days_json
      - البحث عن المريض عبر booking_id أولاً، وإن لم يُرسل أو لم يُطابق وجِد patient_id يُستخدم كبديل.
      - تحويل القيمة الإنجليزية للعربية إن وُجدت في STATUS_MAP، وإلا تبقى كما هي.
      - تحديث مفتاح status داخل ذلك المريض فقط بدون أي تعديل آخر.
      - حفظ days_json.
    """
    if not payload.booking_id and not payload.patient_id:
        raise HTTPException(status_code=400, detail="يجب إرسال booking_id أو patient_id")

    bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == payload.clinic_id).first()
    if not bt:
        raise HTTPException(status_code=404, detail="لا يوجد جدول حجز لهذه العيادة")

    try:
        days = json.loads(bt.days_json) if bt.days_json else {}
    except Exception:
        days = {}

    target_booking_id = payload.booking_id
    target_patient_id = payload.patient_id

    normalized_status = STATUS_MAP.get(payload.status, payload.status)

    found = None  # (day_key, index_in_patients, old_status)
    for d_key, d_val in days.items():
        if not isinstance(d_val, dict):
            continue
        plist = d_val.get("patients")
        if not isinstance(plist, list):
            continue
        for idx, p in enumerate(plist):
            if not isinstance(p, dict):
                continue
            bid = p.get("booking_id")
            pid = p.get("patient_id")
            if target_booking_id and bid == target_booking_id:
                found = (d_key, idx, p.get("status"))
                break
            if not target_booking_id and target_patient_id and pid == target_patient_id:
                found = (d_key, idx, p.get("status"))
                break
        if found:
            break

    if not found:
        raise HTTPException(status_code=404, detail="المريض المطلوب غير موجود")

    day_key, patient_index, old_status = found
    # تعديل النسخة الموجودة فقط
    days[day_key]["patients"][patient_index]["status"] = normalized_status

    # حفظ بدون أي تغييرات أخرى
    bt.days_json = json.dumps(days, ensure_ascii=False)
    db.add(bt)
    db.commit()

    # إعادة تأكيد القيم من المخزن (بعد التعديل)
    final_booking_id = days[day_key]["patients"][patient_index].get("booking_id")

    return schemas.EditPatientBookingResponse(
        message="تم تحديث الحالة بنجاح",
        clinic_id=payload.clinic_id,
        booking_id=final_booking_id,
        old_status=old_status,
        new_status=normalized_status,
    )
