from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models, schemas
from .doctors import require_profile_secret
from datetime import datetime, timezone, timedelta
import asyncio
import hashlib

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
        
        # مسح الكاش بعد الإنشاء
        from .cache import cache
        cache_key = f"booking:days:clinic:{payload.clinic_id}"
        cache.delete(cache_key)
        
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
    
    # مسح الكاش بعد التحديث
    from .cache import cache
    cache_key = f"booking:days:clinic:{payload.clinic_id}"
    cache.delete(cache_key)
    
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
    """إضافة مريض إلى قائمة الحجز العادي.
    
    للحجز من تطبيق المريض:
    - لا يحتاج إرسال date (سيتم البحث تلقائياً عن أقرب يوم متاح)
    - يبدأ من اليوم الحالي، إذا كان ممتلئاً ينتقل لليوم التالي
    - يفتح تيبل جديد تلقائياً إذا لم يكن موجوداً
    
    للحجز من السكرتير:
    - يجب إرسال date محدد
    """
    
    clinic_id = payload.clinic_id
    if not clinic_id:
        raise HTTPException(status_code=400, detail="يجب إرسال clinic_id")
    
    # جلب جدول الحجز
    bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == clinic_id).first()
    
    # إذا لم يكن هناك جدول، ننشئ واحداً
    if not bt:
        bt = models.BookingTable(
            clinic_id=clinic_id,
            days_json=json.dumps({}, ensure_ascii=False)
        )
        db.add(bt)
        db.commit()

    try:
        days = json.loads(bt.days_json) if bt.days_json else {}
    except Exception:
        days = {}
    
    # تحديد التاريخ المستهدف
    from datetime import datetime as dt, timedelta, timezone as tz
    
    final_date = None
    day_obj = None
    
    # إذا تم تحديد التاريخ صراحة (سكرتير أو مريض)
    if payload.date:
        date_key = payload.date
        
        # إنشاء اليوم إذا لم يكن موجوداً
        if date_key not in days:
            # محاولة الحصول على السعة من آخر يوم موجود
            ref_capacity = 20  # افتراضي
            if days:
                try:
                    last_day = max(days.keys())
                    last_day_obj = days.get(last_day, {})
                    if isinstance(last_day_obj, dict):
                        ref_capacity = last_day_obj.get("capacity_total", 20)
                except Exception:
                    pass
            
            day_obj = {
                "source": payload.source,
                "status": "open",
                "capacity_total": ref_capacity,
                "capacity_used": 0,
                "patients": []
            }
            days[date_key] = day_obj
        else:
            day_obj = days[date_key]
            
            # التحقق من صحة البنية
            if not isinstance(day_obj, dict):
                day_obj = {
                    "source": payload.source,
                    "status": "open",
                    "capacity_total": 20,
                    "capacity_used": 0,
                    "patients": []
                }
                days[date_key] = day_obj
        
        final_date = date_key
    
    # البحث التلقائي عن أقرب يوم متاح (فقط إذا لم يُحدد التاريخ)
    elif payload.source == "patient_app":
        # نبدأ من اليوم الحالي بتوقيت العراق
        from .timezone_utils import now_iraq
        now_dt = now_iraq()
        today_iraq = now_dt.date()
        current_date = today_iraq
        max_days = 30
        
        # جلب أيام عمل العيادة من profile
        doctor = db.query(models.Doctor).filter(models.Doctor.id == clinic_id).first()
        clinic_days_from = None
        clinic_days_to = None
        if doctor and doctor.profile_json:
            try:
                profile = json.loads(doctor.profile_json)
                clinic_days = profile.get("clinic_days", {})
                clinic_days_from = clinic_days.get("from")
                clinic_days_to = clinic_days.get("to")
            except Exception:
                pass
        
        # خريطة الأيام العربية (Python weekday: 0=الاثنين، 6=الأحد)
        arabic_days = {
            0: "الاثنين",   # Monday
            1: "الثلاثاء",  # Tuesday
            2: "الأربعاء",  # Wednesday
            3: "الخميس",   # Thursday
            4: "الجمعة",    # Friday
            5: "السبت",    # Saturday
            6: "الأحد"     # Sunday
        }
        
        # ترتيب الأيام
        day_order = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
        
        # دالة لتوحيد الهمزات
        def normalize_day_name(day_name):
            """توحيد أسماء الأيام لقبول الهمزات بأشكالها المختلفة"""
            if not day_name:
                return day_name
            # توحيد الهمزات: أ ← ا
            normalized = day_name.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
            return normalized
        
        for _ in range(max_days):
            date_str = current_date.strftime("%Y-%m-%d")
            weekday = current_date.weekday()
            day_name_ar = arabic_days.get(weekday)
            
            # التحقق من أيام العمل
            if clinic_days_from and clinic_days_to and day_name_ar:
                try:
                    # توحيد أسماء الأيام للمقارنة
                    norm_from = normalize_day_name(clinic_days_from)
                    norm_to = normalize_day_name(clinic_days_to)
                    norm_current = normalize_day_name(day_name_ar)
                    
                    # إنشاء day_order بدون همزات للمقارنة
                    norm_day_order = [normalize_day_name(d) for d in day_order]
                    
                    from_idx = norm_day_order.index(norm_from)
                    to_idx = norm_day_order.index(norm_to)
                    current_idx = norm_day_order.index(norm_current)
                    
                    # التحقق إذا كان اليوم ضمن نطاق أيام العمل
                    is_working_day = False
                    if from_idx <= to_idx:
                        is_working_day = from_idx <= current_idx <= to_idx
                    else:  # نطاق يمر عبر نهاية الأسبوع
                        is_working_day = current_idx >= from_idx or current_idx <= to_idx
                    
                    if not is_working_day:
                        current_date += timedelta(days=1)
                        continue
                except Exception:
                    pass
            
            date_str = current_date.strftime("%Y-%m-%d")
            
            # التحقق إذا كان اليوم موجوداً
            if date_str in days:
                day_obj = days.get(date_str)
                if isinstance(day_obj, dict):
                    # تخطي الأيام المغلقة (عطلات)
                    day_status = day_obj.get("status", "open")
                    if day_status == "closed":
                        current_date += timedelta(days=1)
                        continue
                    
                    capacity_total = day_obj.get("capacity_total", 20)
                    
                    # حساب السعة الفعلية (بدون الحجوزات الملغاة)
                    patients_list = day_obj.get("patients", [])
                    active_patients_count = sum(
                        1 for p in patients_list 
                        if isinstance(p, dict) and p.get("status") != "ملغى"
                    )
                    
                    # إذا كان هناك مكان متاح (نحسب الفعليين فقط، وليس capacity_used)
                    if active_patients_count < capacity_total:
                        # التحقق من عدم تكرار patient_id (إذا كان محدداً) - نتجاهل الملغاة
                        if payload.patient_id:
                            patients = day_obj.get("patients", [])
                            # فقط الحجوزات النشطة (غير الملغاة)
                            is_duplicate = any(
                                isinstance(p, dict) and 
                                p.get("patient_id") == payload.patient_id and 
                                p.get("status") != "ملغى"
                                for p in patients
                            )
                            if not is_duplicate:
                                final_date = date_str
                                break
                        else:
                            final_date = date_str
                            break
            else:
                # اليوم غير موجود، ننشئ تيبل جديد
                # محاولة الحصول على السعة من آخر يوم موجود
                ref_capacity = 20  # افتراضي
                if days:
                    try:
                        last_day = max(days.keys())
                        last_day_obj = days.get(last_day, {})
                        if isinstance(last_day_obj, dict):
                            ref_capacity = last_day_obj.get("capacity_total", 20)
                    except Exception:
                        pass
                
                day_obj = {
                    "source": "patient_app",
                    "status": "open",
                    "capacity_total": ref_capacity,
                    "capacity_used": 0,
                    "patients": []
                }
                days[date_str] = day_obj
                final_date = date_str
                break
            
            # الانتقال لليوم التالي
            current_date += timedelta(days=1)
        
        if final_date is None:
            raise HTTPException(
                status_code=400, 
                detail=f"لا يوجد أيام متاحة خلال الـ {max_days} يوم القادمة"
            )
    else:
        # السكرتير بدون تاريخ - خطأ
        raise HTTPException(status_code=400, detail="يجب تحديد التاريخ")
    
    # الآن لدينا final_date و day_obj
    date_key = final_date
    day_obj = days[date_key]
    
    # التحقق من الحقول الأساسية
    patients_list = day_obj.get("patients", [])
    if not isinstance(patients_list, list):
        patients_list = []
    
    # توليد patient_id للمريض إذا لم يُرسل
    auto_patient_id_for_patient_app: str | None = None
    if not payload.patient_id:
        # حساب التسلسل العام
        max_num = 100
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
    
    # منع تكرار نفس patient_id في نفس التاريخ (نتجاهل الحجوزات الملغاة)
    if payload.patient_id:
        for p in patients_list:
            if isinstance(p, dict) and p.get("patient_id") == payload.patient_id:
                # إذا كان المريض موجود لكن حجزه ملغى، نسمح بالحجز الجديد
                if p.get("status") != "ملغى":
                    raise HTTPException(status_code=409, detail="هذا المريض محجوز مسبقاً في هذا التاريخ")

    capacity_total = int(day_obj.get("capacity_total", 20))
    
    # حساب عدد الحجوزات النشطة (غير الملغاة) للحصول على التوكن الجديد
    active_patients = [
        p for p in patients_list 
        if isinstance(p, dict) and p.get("status") != "ملغى"
    ]
    next_token = len(active_patients) + 1
    
    # توليد booking_id جديد
    seq = len(patients_list) + 1
    date_compact = date_key.replace('-', '')
    if payload.source == "secretary_app":
        booking_id = f"S-{clinic_id}-{date_compact}-{seq:03d}"
    else:
        booking_id = f"B-{clinic_id}-{date_compact}-{seq:04d}"

    # تحديد patient_id النهائي
    if payload.source == "secretary_app" and not payload.patient_id:
        suffix = booking_id.split('-')[-1]
        if len(suffix) == 3 and suffix.isdigit():
            payload.patient_id = suffix
        else:
            payload.patient_id = auto_patient_id_for_patient_app or "P-101"
    elif not payload.patient_id:
        payload.patient_id = auto_patient_id_for_patient_app

    # حالة الحجز
    raw_status = payload.status or "booked"
    status_ar = STATUS_MAP.get(raw_status, raw_status)

    # created_at
    created_at = payload.created_at or dt.now(timezone.utc).isoformat()

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

    # إضافة الحجز الجديد دائماً في النهاية (الملغى يبقى لكن بدون token)
    patients_list.append(patient_entry)
    
    # تحديث السعة المستخدمة = عدد الحجوزات النشطة
    day_obj["capacity_used"] = next_token
    day_obj["patients"] = patients_list
    days[date_key] = day_obj

    # حفظ
    try:
        bt.days_json = json.dumps(days, ensure_ascii=False)
        db.add(bt)
        db.commit()
        db.refresh(bt)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"خطأ في حفظ البيانات: {str(e)}")
    
    # حذف الكاش بعد التحديث
    from .cache import cache
    cache.delete_pattern(f"booking:days:clinic:{clinic_id}")

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
        
        # مسح الكاش بعد الإضافة
        from .cache import cache
        cache_key = f"booking:days:clinic:{payload.clinic_id}"
        cache.delete(cache_key)
        
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
    
    # مسح الكاش بعد الإضافة
    from .cache import cache
    cache_key = f"booking:days:clinic:{payload.clinic_id}"
    cache.delete(cache_key)
    
    return schemas.AddDayResponse(
        status="تم الانشاء بنجاح",
        message=f"تمت إضافة اليوم الجديد: {new_date_str}",
        date_added=new_date_str
    )


def _load_days_raw(db: Session, clinic_id: int) -> dict:
    bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == clinic_id).first()
    if not bt:
        raise HTTPException(status_code=404, detail="لا يوجد جدول حجز لهذه العيادة")
    try:
        return json.loads(bt.days_json) if bt.days_json else {}
    except Exception:
        return {}


def _clean_days(days: dict) -> dict:
    # إزالة inline_next، وتنظيف clinic_id/date داخل المرضى، وترتيب المفاتيح
    cleaned_days: dict = {}
    for d_key in sorted(days.keys()):
        d_val = days.get(d_key)
        if not isinstance(d_val, dict):
            cleaned_days[d_key] = d_val
            continue
        if "inline_next" in d_val:
            d_val = {k: v for k, v in d_val.items() if k != "inline_next"}
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
    return cleaned_days


@router.get("/booking_days", response_model=schemas.BookingDaysFullResponse)
async def get_booking_days(
    clinic_id: int,
    request: Request,
    stream: bool = False,
    heartbeat: int = 15,
    timeout: int = 300,
    poll_interval: float = 1.0,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret),
):
    """إرجاع الأيام كـ JSON كما هو معتاد، أو كبث SSE إذا طُلب.

    - الوضع الافتراضي: JSON (سلوك قديم بدون تغيير) + Caching للأداء
    - إذا stream=true أو كان Accept يحتوي text/event-stream: بث SSE
    """

    wants_sse = stream or ("text/event-stream" in (request.headers.get("accept", "").lower()))
    if not wants_sse:
        # محاولة الحصول من الكاش أولاً
        from .cache import cache
        cache_key = f"booking:days:clinic:{clinic_id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return schemas.BookingDaysFullResponse(clinic_id=clinic_id, days=cached_data)
        
        # إذا لم يوجد في الكاش، اقرأ من Database
        days = _load_days_raw(db, clinic_id)
        cleaned = _clean_days(days)
        
        # حفظ في الكاش لمدة 30 ثانية
        cache.set(cache_key, cleaned, ttl=30)
        
        return schemas.BookingDaysFullResponse(clinic_id=clinic_id, days=cleaned)

    async def event_gen():
        # لقطة أولية + تحديثات عند تغيّر الهاش + ping دوري
        # نستخدم session منفصل لكل استعلام لتجنب حبس الاتصالات
        local_db = SessionLocal()
        try:
            days = _load_days_raw(local_db, clinic_id)
            cleaned = _clean_days(days)
            last_hash = hashlib.sha1(json.dumps(cleaned, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
            payload = json.dumps({"clinic_id": clinic_id, "days": cleaned, "hash": last_hash}, ensure_ascii=False)
            yield f"event: snapshot\ndata: {payload}\n\n"

            start = datetime.now(timezone.utc)
            last_ping = start
            while True:
                # timeout
                if (datetime.now(timezone.utc) - start).total_seconds() > timeout:
                    yield "event: bye\ndata: timeout\n\n"
                    break
                # تحقق دوري للتغيّر - نستخدم session جديد في كل مرة
                await asyncio.sleep(poll_interval)
                temp_db = SessionLocal()
                try:
                    days = _load_days_raw(temp_db, clinic_id)
                    cleaned = _clean_days(days)
                    cur_hash = hashlib.sha1(json.dumps(cleaned, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
                    if cur_hash != last_hash:
                        last_hash = cur_hash
                        payload = json.dumps({"clinic_id": clinic_id, "days": cleaned, "hash": last_hash}, ensure_ascii=False)
                        yield f"event: update\ndata: {payload}\n\n"
                finally:
                    temp_db.close()
                # ping
                if (datetime.now(timezone.utc) - last_ping).total_seconds() >= heartbeat:
                    last_ping = datetime.now(timezone.utc)
                    yield f"event: ping\ndata: {json.dumps({'ts': last_ping.timestamp()})}\n\n"
        except Exception as e:
            err = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {err}\n\n"
        finally:
            local_db.close()

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_gen(), media_type="text/event-stream", headers=headers)


@router.post("/edit_patient_booking", response_model=schemas.EditPatientBookingResponse)
def edit_patient_booking(payload: schemas.EditPatientBookingRequest, db: Session = Depends(get_db), _: None = Depends(require_profile_secret)):
    """تعديل حالة مريض بالاعتماد حصراً على booking_id.

    المنطق:
      - booking_id يحتوي التاريخ بالشكل B-<clinic>-<YYYYMMDD>-XXXX أو S-<clinic>-<YYYYMMDD>-NNN
      - نستخرج منه جزء التاريخ (المقطع الثالث بعد التقسيم) للتحقق أن اليوم موجود.
      - نبحث داخل ذلك اليوم عن المريض الذي يحمل نفس booking_id.
      - نحدّث status فقط.
    """
    booking_id = payload.booking_id
    parts = booking_id.split('-')
    if len(parts) < 4:
        raise HTTPException(status_code=400, detail="booking_id غير صالح")
    # الصيغة المتوقعة: PREFIX-clinicId-YYYYMMDD-SEQ
    date_compact = parts[2]
    if len(date_compact) != 8 or not date_compact.isdigit():
        raise HTTPException(status_code=400, detail="جزء التاريخ داخل booking_id غير صالح")
    date_key = f"{date_compact[0:4]}-{date_compact[4:6]}-{date_compact[6:8]}"

    bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == payload.clinic_id).first()
    if not bt:
        raise HTTPException(status_code=404, detail="لا يوجد جدول حجز لهذه العيادة")

    try:
        days = json.loads(bt.days_json) if bt.days_json else {}
    except Exception:
        days = {}

    day_obj = days.get(date_key)
    if not isinstance(day_obj, dict):
        raise HTTPException(status_code=404, detail="اليوم المستخرج من booking_id غير موجود")

    plist = day_obj.get("patients")
    if not isinstance(plist, list):
        raise HTTPException(status_code=404, detail="لا توجد قائمة مرضى لهذا اليوم")

    normalized_status = STATUS_MAP.get(payload.status, payload.status)

    target_index = None
    old_status = None
    patient_id_found = None
    for idx, p in enumerate(plist):
        if isinstance(p, dict) and p.get("booking_id") == booking_id:
            target_index = idx
            old_status = p.get("status")
            patient_id_found = p.get("patient_id")
            break

    if target_index is None:
        raise HTTPException(status_code=404, detail="الحجز غير موجود داخل هذا التاريخ")

    # تحديث الحالة
    cancellation_statuses = ["ملغى", "الغاء الحجز", "cancelled"]
    if normalized_status in cancellation_statuses:
        # تغيير الحالة إلى "ملغى" وإزالة التوكن
        plist[target_index]["status"] = "ملغى"
        plist[target_index]["token"] = None  # إزالة التوكن من الملغى
        
        # إعادة ترقيم الحجوزات النشطة فقط (غير الملغاة)
        active_token = 1
        for p in plist:
            if isinstance(p, dict) and p.get("status") != "ملغى":
                p["token"] = active_token
                
                # تحديث booking_id ليطابق التوكن الجديد
                old_booking_id = p.get("booking_id", "")
                if old_booking_id:
                    parts = old_booking_id.split('-')
                    if len(parts) >= 4:
                        prefix = parts[0]  # B or S
                        clinic = parts[1]
                        date_compact = parts[2]
                        if prefix == "S":
                            p["booking_id"] = f"S-{clinic}-{date_compact}-{active_token:03d}"
                        else:
                            p["booking_id"] = f"B-{clinic}-{date_compact}-{active_token:04d}"
                
                active_token += 1
        
        # تحديث capacity_used (عدد الحجوزات النشطة فقط)
        day_obj["capacity_used"] = active_token - 1
    else:
        # تحديث الحالة فقط
        plist[target_index]["status"] = normalized_status

    day_obj["patients"] = plist
    days[date_key] = day_obj

    bt.days_json = json.dumps(days, ensure_ascii=False)
    db.add(bt)
    db.commit()
    db.refresh(bt)

    # مسح الكاش بعد التعديل لضمان ظهور التغييرات فوراً
    from .cache import cache
    cache_key = f"booking:days:clinic:{payload.clinic_id}"
    cache.delete(cache_key)

    return schemas.EditPatientBookingResponse(
        message="تم تحديث الحالة بنجاح",
        clinic_id=payload.clinic_id,
        booking_id=booking_id,
        old_status=old_status,
        new_status=normalized_status,
        patient_id=patient_id_found
    )


@router.post("/save_table", response_model=schemas.SaveTableResponse)
def save_table(payload: schemas.SaveTableRequest, db: Session = Depends(get_db), _: None = Depends(require_profile_secret)):
    """أرشفة يوم في جدول مستقل booking_archives.

    الحقول: clinic_id + table_date (مفتاح منطقي) + النسخة المبسطة من المرضى.
    - إذا كان هناك صف سابق لنفس (clinic_id, table_date) سنقوم بتحديثه (Upsert logic).
    - patients تُخزن كنص JSON في العمود patients_json.
    """
    # تحقق من الصيغة البسيطة للتاريخ
    try:
        datetime.strptime(payload.table_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="صيغة التاريخ غير صحيحة، يجب YYYY-MM-DD")

    # إذا لم تُرسل الحقول (capacity_total / patients ...) سنستخرجها من booking_tables
    cap_total = payload.capacity_total
    cap_served = payload.capacity_served
    cap_cancelled = payload.capacity_cancelled
    patients_list = payload.patients

    if cap_total is None or patients_list is None:
        bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == payload.clinic_id).first()
        if not bt:
            raise HTTPException(status_code=404, detail="لا يوجد جدول حجز لاستخراج البيانات")
        try:
            days = json.loads(bt.days_json) if bt.days_json else {}
        except Exception:
            days = {}
        day_obj = days.get(payload.table_date)
        if not isinstance(day_obj, dict):
            raise HTTPException(status_code=404, detail="لا يوجد يوم مطابق في الجدول الحالي")
        # استنتاج البيانات
        if cap_total is None:
            cap_total = day_obj.get("capacity_total") or 0
        plist = day_obj.get("patients") if isinstance(day_obj.get("patients"), list) else []
        if patients_list is None:
            patients_list = plist
        if cap_served is None:
            cap_served = sum(1 for p in plist if isinstance(p, dict) and p.get("status") in ("تمت المعاينة", "served"))
        if cap_cancelled is None:
            cap_cancelled = sum(1 for p in plist if isinstance(p, dict) and p.get("status") in ("ملغى", "cancelled"))

    existing = (
        db.query(models.BookingArchive)
        .filter(models.BookingArchive.clinic_id == payload.clinic_id,
                models.BookingArchive.table_date == payload.table_date)
        .first()
    )
    if existing:
        existing.capacity_total = cap_total
        existing.capacity_served = cap_served
        existing.capacity_cancelled = cap_cancelled
        existing.patients_json = json.dumps(patients_list, ensure_ascii=False)
        db.add(existing)
        db.commit()
        
        # مسح الكاش بعد التحديث
        from .cache import cache
        cache_key = f"booking:days:clinic:{payload.clinic_id}"
        cache.delete(cache_key)
        
        return schemas.SaveTableResponse(status="تم تحديث الأرشيف بنجاح")
    else:
        arch = models.BookingArchive(
            clinic_id=payload.clinic_id,
            table_date=payload.table_date,
            capacity_total=cap_total or 0,
            capacity_served=cap_served,
            capacity_cancelled=cap_cancelled,
            patients_json=json.dumps(patients_list or [], ensure_ascii=False)
        )
        db.add(arch)
        db.commit()
        
        # مسح الكاش بعد الإنشاء
        from .cache import cache
        cache_key = f"booking:days:clinic:{payload.clinic_id}"
        cache.delete(cache_key)
        
        return schemas.SaveTableResponse(status="تم إنشاء الأرشيف بنجاح")


@router.get("/booking_archives/{clinic_id}", response_model=schemas.BookingArchivesListResponse)
def list_booking_archives(
    clinic_id: int,
    from_date: str | None = None,  # YYYY-MM-DD
    to_date: str | None = None,    # YYYY-MM-DD
    limit: int | None = None,      # حد أقصى لعدد الأيام المرجعة
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret),
):
    """إرجاع الأيام المؤرشفة لعيادة معينة.

    باراميترات اختيارية:
    - from_date: بداية نطاق التاريخ (شامل)
    - to_date: نهاية نطاق التاريخ (شامل)
    - limit: عدد السجلات القصوى بعد الترتيب تنازلياً
    """
    q = db.query(models.BookingArchive).filter(models.BookingArchive.clinic_id == clinic_id)
    def _valid(d: str) -> bool:
        try:
            datetime.strptime(d, "%Y-%m-%d")
            return True
        except Exception:
            return False
    if from_date:
        if not _valid(from_date):
            raise HTTPException(status_code=400, detail="صيغة from_date غير صحيحة")
        q = q.filter(models.BookingArchive.table_date >= from_date)
    if to_date:
        if not _valid(to_date):
            raise HTTPException(status_code=400, detail="صيغة to_date غير صحيحة")
        q = q.filter(models.BookingArchive.table_date <= to_date)
    q = q.order_by(models.BookingArchive.table_date.desc())
    if limit and limit > 0:
        q = q.limit(limit)
    rows = q.all()
    items: list[schemas.BookingArchiveItem] = []
    for r in rows:
        try:
            patients = json.loads(r.patients_json) if r.patients_json else []
            if not isinstance(patients, list):
                patients = []
        except Exception:
            patients = []
        items.append(
            schemas.BookingArchiveItem(
                table_date=r.table_date,
                capacity_total=r.capacity_total,
                capacity_served=r.capacity_served,
                capacity_cancelled=r.capacity_cancelled,
                patients=patients,
            )
        )
    return schemas.BookingArchivesListResponse(clinic_id=clinic_id, items=items)


@router.get("/all_days", response_model=schemas.AllDaysResponse)
def get_all_days(clinic_id: int, db: Session = Depends(get_db), _: None = Depends(require_profile_secret)):
    """إرجاع جميع الأيام الحالية (غير المؤرشفة) من جدول booking_tables.

    الشكل:
    {
      "clinic_id": <id>,
      "days": {
         "2025-11-14": {
            "capacity_total": 600,
            "capacity_served": 0,
            "capacity_cancelled": 0,
            "capacity_used": 0,
            "status": "open",
            "patients": [...]
         },
         ...
      }
    }
    """
    # جلب جدول الحجوزات الحالي (غير المؤرشف)
    bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == clinic_id).first()
    
    if not bt:
        return schemas.AllDaysResponse(clinic_id=clinic_id, days={})
    
    try:
        days = json.loads(bt.days_json) if bt.days_json else {}
        if not isinstance(days, dict):
            days = {}
    except Exception:
        days = {}
    
    return schemas.AllDaysResponse(clinic_id=clinic_id, days=days)


@router.post("/close_table", response_model=schemas.CloseTableResponse)
def close_table(payload: schemas.CloseTableRequest, db: Session = Depends(get_db), _: None = Depends(require_profile_secret)):
    """تغيير حالة يوم إلى "closed"، حفظه في الأرشيف، ثم حذفه من الجدول.
    
    الخطوات:
    1. تغيير status إلى "closed"
    2. حفظ التغيير
    3. حفظ اليوم في الأرشيف (BookingArchive)
    4. حذف اليوم من days_json
    """
    bt = db.query(models.BookingTable).filter(models.BookingTable.clinic_id == payload.clinic_id).first()
    if not bt:
        raise HTTPException(status_code=404, detail="لا يوجد جدول حجز لهذه العيادة")
    try:
        days = json.loads(bt.days_json) if bt.days_json else {}
    except Exception:
        days = {}

    if payload.date not in days:
        raise HTTPException(status_code=404, detail="التاريخ غير موجود")

    day_obj = days[payload.date]
    if not isinstance(day_obj, dict):
        raise HTTPException(status_code=400, detail="بنية اليوم غير صالحة")

    # الخطوة 1: تغيير حالة جميع المرضى إلى "ملغى"
    patients_list = day_obj.get("patients", [])
    for patient in patients_list:
        if isinstance(patient, dict):
            # تغيير حالة المرضى الذين لم تتم معاينتهم إلى ملغى
            if patient.get("status") not in ("تمت المعاينة", "served"):
                patient["status"] = "ملغى"
    
    day_obj["patients"] = patients_list
    
    # تغيير الحالة إلى closed
    day_obj["status"] = "closed"
    days[payload.date] = day_obj
    
    # حفظ التغيير مؤقتاً (لتسجيل أن اليوم أُغلق)
    bt.days_json = json.dumps(days, ensure_ascii=False)
    db.add(bt)
    db.commit()

    # الخطوة 2: حفظ اليوم في الأرشيف
    patients_list = day_obj.get("patients", [])
    capacity_total = day_obj.get("capacity_total", 0)
    capacity_served = sum(1 for p in patients_list if isinstance(p, dict) and p.get("status") in ("تمت المعاينة", "served"))
    capacity_cancelled = sum(1 for p in patients_list if isinstance(p, dict) and p.get("status") in ("ملغى", "cancelled"))
    
    # التحقق إذا كان اليوم موجود في الأرشيف
    existing = (
        db.query(models.BookingArchive)
        .filter(models.BookingArchive.clinic_id == payload.clinic_id,
                models.BookingArchive.table_date == payload.date)
        .first()
    )
    
    if existing:
        # تحديث الأرشيف الموجود
        existing.capacity_total = capacity_total
        existing.capacity_served = capacity_served
        existing.capacity_cancelled = capacity_cancelled
        existing.patients_json = json.dumps(patients_list, ensure_ascii=False)
        db.add(existing)
    else:
        # إنشاء سجل جديد في الأرشيف
        arch = models.BookingArchive(
            clinic_id=payload.clinic_id,
            table_date=payload.date,
            capacity_total=capacity_total,
            capacity_served=capacity_served,
            capacity_cancelled=capacity_cancelled,
            patients_json=json.dumps(patients_list, ensure_ascii=False)
        )
        db.add(arch)
    db.commit()

    # الخطوة 3: حذف اليوم من الجدول
    days.pop(payload.date)
    
    # استبعاد المفاتيح المؤرشفة من العد
    remaining_booking_days = [k for k in days.keys() if not k.startswith("_archived_")]

    if not remaining_booking_days:
        # حذف السجل كاملاً إذا لم يتبق أيام
        db.delete(bt)
        db.commit()
        
        # مسح الكاش بعد الحذف
        from .cache import cache
        cache_key = f"booking:days:clinic:{payload.clinic_id}"
        cache.delete(cache_key)
        
        return schemas.CloseTableResponse(
            status="تم إغلاق وحفظ اليوم في الأرشيف، وحذف القائمة بالكامل",
            removed_all=True
        )
    
    # تحديث السجل بعد الحذف
    bt.days_json = json.dumps(days, ensure_ascii=False)
    db.add(bt)
    db.commit()
    
    # مسح الكاش بعد التحديث
    from .cache import cache
    cache_key = f"booking:days:clinic:{payload.clinic_id}"
    cache.delete(cache_key)
    
    return schemas.CloseTableResponse(
        status="تم إغلاق وحفظ اليوم في الأرشيف بنجاح",
        removed_all=False
    )
