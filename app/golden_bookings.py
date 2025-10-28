from __future__ import annotations
import json
import random
import asyncio
import hashlib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from .database import SessionLocal
from . import models, schemas
from .doctors import require_profile_secret

# خريطة تحويل الحالات من إنجليزي إلى عربي
STATUS_MAP = {
    "booked": "تم الحجز",
    "served": "تمت المعاينة",
    "no_show": "لم يحضر",
    "cancelled": "ملغى",
    "in_progress": "جاري المعاينة",
}

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
    
    # مسح الكاش بعد الإنشاء أو التحديث
    from .cache import cache
    cache_key = f"golden:days:clinic:{payload.clinic_id}"
    cache.delete(cache_key)
    
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
    """حجز مريض في Golden Book مع توليد كود 4 أرقام فريد.
    
    يدعم وضعين:
    1. auto_assign=True (افتراضي): يبحث عن أقرب يوم متاح بدءاً من التاريخ المطلوب
    2. auto_assign=False: يحجز في التاريخ المحدد فقط (يفشل إذا كان ممتلئاً)
    """
    
    # البحث عن الجدول
    gt = db.query(models.GoldenBookingTable).filter(
        models.GoldenBookingTable.clinic_id == payload.clinic_id
    ).first()
    
    # إذا لم يكن هناك جدول على الإطلاق، ننشئ واحداً
    if not gt:
        gt = models.GoldenBookingTable(
            clinic_id=payload.clinic_id,
            days_json=json.dumps({}, ensure_ascii=False)
        )
        db.add(gt)
        db.commit()
    
    try:
        days = json.loads(gt.days_json) if gt.days_json else {}
    except Exception:
        days = {}
    
    # التحقق من صيغة التاريخ
    from datetime import datetime as dt, timedelta
    
    try:
        requested_date = dt.strptime(payload.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="صيغة التاريخ غير صحيحة (يجب YYYY-MM-DD)")
    
    final_date = None
    day_obj = None
    
    # الوضع 1: الحجز في تاريخ محدد فقط (auto_assign=False)
    if not payload.auto_assign:
        date_str = payload.date
        
        # التحقق إذا كان اليوم موجوداً
        if date_str not in days:
            # إنشاء اليوم إذا لم يكن موجوداً
            day_obj = {
                "source": "patient_app",
                "status": "open",
                "capacity_total": 5,
                "capacity_used": 0,
                "patients": []
            }
            days[date_str] = day_obj
            final_date = date_str
        else:
            day_obj = days.get(date_str)
            if not isinstance(day_obj, dict):
                raise HTTPException(status_code=400, detail="بنية اليوم غير صالحة")
            
            capacity_total = day_obj.get("capacity_total", 5)
            capacity_used = day_obj.get("capacity_used", 0)
            
            # التحقق من السعة
            if capacity_used >= capacity_total:
                raise HTTPException(
                    status_code=400, 
                    detail=f"اليوم {date_str} ممتلئ ({capacity_used}/{capacity_total}). جرب تاريخاً آخر أو استخدم auto_assign=true"
                )
            
            # التحقق من عدم تكرار patient_id
            patients = day_obj.get("patients", [])
            if not isinstance(patients, list):
                patients = []
            
            is_duplicate = any(
                isinstance(p, dict) and p.get("patient_id") == payload.patient_id 
                for p in patients
            )
            
            if is_duplicate:
                raise HTTPException(
                    status_code=409, 
                    detail=f"المريض {payload.patient_id} محجوز مسبقاً في {date_str}"
                )
            
            final_date = date_str
    
    # الوضع 2: البحث التلقائي عن أقرب يوم متاح (auto_assign=True)
    else:
        current_date = requested_date
        max_days_to_check = 30  # نتحقق من 30 يوم كحد أقصى
        
        for _ in range(max_days_to_check):
            date_str = current_date.strftime("%Y-%m-%d")
            
            # التحقق إذا كان اليوم موجوداً
            if date_str in days:
                day_obj = days.get(date_str)
                if isinstance(day_obj, dict):
                    capacity_total = day_obj.get("capacity_total", 5)
                    capacity_used = day_obj.get("capacity_used", 0)
                    
                    # إذا كان هناك مكان متاح
                    if capacity_used < capacity_total:
                        # التحقق من عدم تكرار patient_id
                        patients = day_obj.get("patients", [])
                        if not isinstance(patients, list):
                            patients = []
                        
                        is_duplicate = any(
                            isinstance(p, dict) and p.get("patient_id") == payload.patient_id 
                            for p in patients
                        )
                        
                        if not is_duplicate:
                            final_date = date_str
                            break
            else:
                # اليوم غير موجود، ننشئ جدول جديد
                day_obj = {
                    "source": "patient_app",
                    "status": "open",
                    "capacity_total": 5,
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
                detail=f"لا يوجد أيام متاحة خلال الـ {max_days_to_check} يوم القادمة"
            )
    
    # الآن لدينا final_date و day_obj
    day_obj = days[final_date]
    patients = day_obj.get("patients", [])
    if not isinstance(patients, list):
        patients = []
    
    capacity_total = day_obj.get("capacity_total", 5)
    capacity_used = day_obj.get("capacity_used", 0)
    
    # جمع الأكواد الموجودة حالياً لليوم
    existing_codes = {p.get("code") for p in patients if isinstance(p, dict) and p.get("code")}
    
    # توليد كود فريد
    new_code = _generate_unique_code(existing_codes)
    
    # حساب التوكن التالي
    next_token = max([p.get("token", 0) for p in patients if isinstance(p, dict)], default=0) + 1
    
    # تاريخ الحجز بصيغة ISO
    date_compact = final_date.replace("-", "")  # YYYYMMDD
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
    
    days[final_date] = day_obj
    gt.days_json = json.dumps(days, ensure_ascii=False)
    
    db.add(gt)
    db.commit()
    db.refresh(gt)
    
    # حذف الكاش بعد التحديث
    from .cache import cache
    cache.delete_pattern(f"golden:days:clinic:{payload.clinic_id}")
    
    # رسالة توضح إذا تم الحجز في يوم مختلف
    message = f"تم الحجز بنجاح بأسم: {payload.name}"
    if payload.auto_assign and final_date != payload.date:
        message += f" (تم الحجز في {final_date} لأن {payload.date} كان ممتلئاً)"
    
    return schemas.GoldenBookingResponse(
        message=message,
        code=new_code,
        booking_id=booking_id,
        token=next_token,
        capacity_used=capacity_used + 1,
        capacity_total=capacity_total,
        status="تم الحجز",
        clinic_id=payload.clinic_id,
        date=final_date,  # التاريخ الفعلي للحجز
        patient_id=payload.patient_id
    )


def _load_days_raw_golden(db: Session, clinic_id: int) -> dict:
    """تحميل أيام Golden Book من قاعدة البيانات."""
    gt = db.query(models.GoldenBookingTable).filter(
        models.GoldenBookingTable.clinic_id == clinic_id
    ).first()
    if not gt:
        raise HTTPException(status_code=404, detail="لا يوجد جدول Golden لهذه العيادة")
    try:
        return json.loads(gt.days_json) if gt.days_json else {}
    except Exception:
        return {}


def _clean_days_golden(days: dict) -> dict:
    """تنظيف بيانات الأيام: إزالة حقول زائدة وترتيب المفاتيح."""
    cleaned_days: dict = {}
    for d_key in sorted(days.keys()):
        d_val = days.get(d_key)
        if not isinstance(d_val, dict):
            cleaned_days[d_key] = d_val
            continue
        # إزالة inline_next إن وجد
        if "inline_next" in d_val:
            d_val = {k: v for k, v in d_val.items() if k != "inline_next"}
        # تنظيف بيانات المرضى
        patients = d_val.get("patients")
        if isinstance(patients, list):
            new_list = []
            for p in patients:
                if isinstance(p, dict):
                    # إزالة clinic_id و date من بيانات المريض إن كانت موجودة
                    if "clinic_id" in p or "date" in p:
                        p = {k: v for k, v in p.items() if k not in ("clinic_id", "date")}
                new_list.append(p)
            d_val["patients"] = new_list
        cleaned_days[d_key] = d_val
    return cleaned_days


@router.get("/booking_golden_days", response_model=schemas.BookingDaysFullResponse)
async def get_golden_booking_days(
    clinic_id: int,
    request: Request,
    stream: bool = False,
    heartbeat: int = 15,
    timeout: int = 300,
    poll_interval: float = 1.0,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """إرجاع أيام Golden Book كـ JSON كما هو معتاد، أو كبث SSE إذا طُلب.

    - الوضع الافتراضي: JSON (سلوك قديم بدون تغيير)
    - إذا stream=true أو كان Accept يحتوي text/event-stream: بث SSE
    """

    wants_sse = stream or ("text/event-stream" in (request.headers.get("accept", "").lower()))
    if not wants_sse:
        # محاولة الحصول من الكاش أولاً
        from .cache import cache
        cache_key = f"golden:days:clinic:{clinic_id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return schemas.BookingDaysFullResponse(clinic_id=clinic_id, days=cached_data)
        
        # إذا لم يوجد في الكاش، اقرأ من Database
        days = _load_days_raw_golden(db, clinic_id)
        cleaned = _clean_days_golden(days)
        
        # حفظ في الكاش لمدة 30 ثانية
        cache.set(cache_key, cleaned, ttl=30)
        
        return schemas.BookingDaysFullResponse(clinic_id=clinic_id, days=cleaned)

    async def event_gen():
        # لقطة أولية + تحديثات عند تغيّر الهاش + ping دوري
        # نستخدم session منفصل لكل استعلام لتجنب حبس الاتصالات
        local_db = SessionLocal()
        try:
            days = _load_days_raw_golden(local_db, clinic_id)
            cleaned = _clean_days_golden(days)
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
                    days = _load_days_raw_golden(temp_db, clinic_id)
                    cleaned = _clean_days_golden(days)
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


@router.get("/booking_golden_days_old", response_model=dict)
def get_golden_booking_days_old(
    clinic_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """[مهمل] إرجاع كل أيام Golden Book لعيادة معينة (نسخة قديمة بدون streaming).
    
    مشابه تماماً لـ /booking_days - يرجع 404 إذا لم يوجد جدول.
    """
    gt = db.query(models.GoldenBookingTable).filter(
        models.GoldenBookingTable.clinic_id == clinic_id
    ).first()
    
    if not gt:
        raise HTTPException(status_code=404, detail="لا يوجد جدول Golden لهذه العيادة")
    
    try:
        days = json.loads(gt.days_json) if gt.days_json else {}
    except Exception:
        days = {}
    
    # تنظيف البيانات (إزالة حقول زائدة إن وجدت)
    cleaned_days: dict = {}
    for d_key in sorted(days.keys()):
        d_val = days.get(d_key)
        if not isinstance(d_val, dict):
            cleaned_days[d_key] = d_val
            continue
        # إزالة حقول داخلية إن وجدت
        patients = d_val.get("patients")
        if isinstance(patients, list):
            new_list = []
            for p in patients:
                if isinstance(p, dict):
                    # إزالة clinic_id و date من بيانات المريض إن كانت موجودة
                    if "clinic_id" in p or "date" in p:
                        p = {k: v for k, v in p.items() if k not in ("clinic_id", "date")}
                new_list.append(p)
            d_val["patients"] = new_list
        cleaned_days[d_key] = d_val
    
    return {"clinic_id": clinic_id, "days": cleaned_days}


@router.post("/save_table_gold", response_model=schemas.SaveTableResponse)
def save_table_gold(
    payload: schemas.SaveTableRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """أرشفة يوم Golden Book في جدول مستقل golden_booking_archives.

    مشابه لـ save_table العادي لكن للـ Golden Book.
    """
    # تحقق من الصيغة البسيطة للتاريخ
    try:
        datetime.strptime(payload.table_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="صيغة التاريخ غير صحيحة، يجب YYYY-MM-DD")

    # إذا لم تُرسل الحقول سنستخرجها من golden_booking_tables
    cap_total = payload.capacity_total
    cap_served = payload.capacity_served
    cap_cancelled = payload.capacity_cancelled
    patients_list = payload.patients

    if cap_total is None or patients_list is None:
        gt = db.query(models.GoldenBookingTable).filter(
            models.GoldenBookingTable.clinic_id == payload.clinic_id
        ).first()
        if not gt:
            raise HTTPException(status_code=404, detail="لا يوجد جدول Golden لاستخراج البيانات")
        try:
            days = json.loads(gt.days_json) if gt.days_json else {}
        except Exception:
            days = {}
        day_obj = days.get(payload.table_date)
        if not isinstance(day_obj, dict):
            raise HTTPException(status_code=404, detail="لا يوجد يوم مطابق في الجدول Golden")
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
        db.query(models.GoldenBookingArchive)
        .filter(models.GoldenBookingArchive.clinic_id == payload.clinic_id,
                models.GoldenBookingArchive.table_date == payload.table_date)
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
        cache_key = f"golden:days:clinic:{payload.clinic_id}"
        cache.delete(cache_key)
        
        return schemas.SaveTableResponse(status="تم تحديث أرشيف Golden بنجاح")
    else:
        arch = models.GoldenBookingArchive(
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
        cache_key = f"golden:days:clinic:{payload.clinic_id}"
        cache.delete(cache_key)
        
        return schemas.SaveTableResponse(status="تم إنشاء أرشيف Golden بنجاح")


@router.post("/close_table_gold", response_model=schemas.CloseTableResponse)
def close_table_gold(
    payload: schemas.CloseTableRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """تغيير حالة يوم Golden إلى "closed"، حفظه في الأرشيف، ثم حذفه من الجدول.
    
    الخطوات:
    1. تغيير status إلى "closed"
    2. حفظ التغيير
    3. حفظ اليوم في الأرشيف (GoldenBookingArchive)
    4. حذف اليوم من days_json
    """
    gt = db.query(models.GoldenBookingTable).filter(
        models.GoldenBookingTable.clinic_id == payload.clinic_id
    ).first()
    
    if not gt:
        raise HTTPException(status_code=404, detail="لا يوجد جدول Golden لهذه العيادة")
    
    try:
        days = json.loads(gt.days_json) if gt.days_json else {}
    except Exception:
        days = {}

    if payload.date not in days:
        raise HTTPException(status_code=404, detail="التاريخ غير موجود في Golden table")

    day_obj = days[payload.date]
    if not isinstance(day_obj, dict):
        raise HTTPException(status_code=400, detail="بنية اليوم غير صالحة")

    # الخطوة 1: تغيير الحالة إلى closed
    day_obj["status"] = "closed"
    days[payload.date] = day_obj
    
    # حفظ التغيير مؤقتاً (لتسجيل أن اليوم أُغلق)
    gt.days_json = json.dumps(days, ensure_ascii=False)
    db.add(gt)
    db.commit()

    # الخطوة 2: حفظ اليوم في الأرشيف
    patients_list = day_obj.get("patients", [])
    capacity_total = day_obj.get("capacity_total", 0)
    capacity_served = sum(1 for p in patients_list if isinstance(p, dict) and p.get("status") in ("تمت المعاينة", "served"))
    capacity_cancelled = sum(1 for p in patients_list if isinstance(p, dict) and p.get("status") in ("ملغى", "cancelled"))
    
    # التحقق إذا كان اليوم موجود في الأرشيف
    existing = (
        db.query(models.GoldenBookingArchive)
        .filter(models.GoldenBookingArchive.clinic_id == payload.clinic_id,
                models.GoldenBookingArchive.table_date == payload.date)
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
        arch = models.GoldenBookingArchive(
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
    
    if not days:
        # حذف السجل كاملاً إذا لم يتبق أيام
        db.delete(gt)
        db.commit()
        
        # مسح الكاش بعد الحذف
        from .cache import cache
        cache_key = f"golden:days:clinic:{payload.clinic_id}"
        cache.delete(cache_key)
        
        return schemas.CloseTableResponse(
            status="تم إغلاق وحفظ يوم Golden في الأرشيف، وحذف القائمة بالكامل",
            removed_all=True
        )
    
    # تحديث السجل بعد الحذف
    gt.days_json = json.dumps(days, ensure_ascii=False)
    db.add(gt)
    db.commit()
    
    # مسح الكاش بعد التحديث
    from .cache import cache
    cache_key = f"golden:days:clinic:{payload.clinic_id}"
    cache.delete(cache_key)
    
    return schemas.CloseTableResponse(
        status="تم إغلاق وحفظ يوم Golden في الأرشيف بنجاح",
        removed_all=False
    )


@router.post("/edit_patient_gold_booking", response_model=schemas.EditPatientBookingResponse)
def edit_patient_gold_booking(
    payload: schemas.EditPatientBookingRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """تعديل حالة مريض في Golden Book بالاعتماد على booking_id.

    المنطق:
      - booking_id يحتوي التاريخ بالشكل G-<clinic>-<YYYYMMDD>-<patient_id>
      - نستخرج منه جزء التاريخ (المقطع الثالث بعد التقسيم)
      - نبحث داخل ذلك اليوم عن المريض الذي يحمل نفس booking_id
      - نحدّث status فقط
    """
    booking_id = payload.booking_id
    parts = booking_id.split('-')
    if len(parts) < 4:
        raise HTTPException(status_code=400, detail="booking_id غير صالح")
    
    # الصيغة المتوقعة: G-clinicId-YYYYMMDD-patient_id
    date_compact = parts[2]
    if len(date_compact) != 8 or not date_compact.isdigit():
        raise HTTPException(status_code=400, detail="جزء التاريخ داخل booking_id غير صالح")
    date_key = f"{date_compact[0:4]}-{date_compact[4:6]}-{date_compact[6:8]}"

    gt = db.query(models.GoldenBookingTable).filter(
        models.GoldenBookingTable.clinic_id == payload.clinic_id
    ).first()
    
    if not gt:
        raise HTTPException(status_code=404, detail="لا يوجد جدول Golden لهذه العيادة")

    try:
        days = json.loads(gt.days_json) if gt.days_json else {}
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
        raise HTTPException(status_code=404, detail="الحجز الذهبي غير موجود داخل هذا التاريخ")

    plist[target_index]["status"] = normalized_status
    day_obj["patients"] = plist
    days[date_key] = day_obj

    gt.days_json = json.dumps(days, ensure_ascii=False)
    db.add(gt)
    db.commit()
    db.refresh(gt)

    # مسح الكاش بعد التعديل لضمان ظهور التغييرات فوراً
    from .cache import cache
    cache_key = f"golden:days:clinic:{payload.clinic_id}"
    cache.delete(cache_key)

    return schemas.EditPatientBookingResponse(
        message="تم تحديث حالة الحجز الذهبي بنجاح",
        clinic_id=payload.clinic_id,
        booking_id=booking_id,
        old_status=old_status,
        new_status=normalized_status,
        patient_id=patient_id_found
    )


@router.post("/verify_golden_code", response_model=schemas.VerifyGoldenCodeResponse)
def verify_golden_code(
    payload: schemas.VerifyGoldenCodeRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """التحقق من كود Golden Book المكون من 4 أرقام وإرجاع بيانات المريض.
    
    يستقبل:
    - clinic_id: معرف العيادة
    - code: الكود المكون من 4 أرقام
    - date: (اختياري) التاريخ بصيغة YYYY-MM-DD - إذا لم يُرسل نبحث في كل التواريخ
    
    يرجع:
    - بيانات المريض إذا وُجد الكود
    - رسالة خطأ إذا لم يُوجد
    """
    # البحث عن جدول Golden Book
    gt = db.query(models.GoldenBookingTable).filter(
        models.GoldenBookingTable.clinic_id == payload.clinic_id
    ).first()
    
    if not gt:
        return schemas.VerifyGoldenCodeResponse(
            status="error",
            message="لا يوجد جدول Golden لهذه العيادة"
        )
    
    try:
        days = json.loads(gt.days_json) if gt.days_json else {}
    except Exception:
        days = {}
    
    # إذا تم تحديد تاريخ معين، نبحث فيه فقط
    if payload.date:
        search_dates = [payload.date]
    else:
        # البحث في كل التواريخ
        search_dates = list(days.keys())
    
    # البحث عن الكود في التواريخ المحددة
    for date_key in search_dates:
        day_obj = days.get(date_key)
        if not isinstance(day_obj, dict):
            continue
        
        patients = day_obj.get("patients", [])
        if not isinstance(patients, list):
            continue
        
        # البحث عن المريض بالكود
        for patient in patients:
            if not isinstance(patient, dict):
                continue
            
            if patient.get("code") == payload.code:
                # وجدنا المريض!
                return schemas.VerifyGoldenCodeResponse(
                    status="success",
                    patient_name=patient.get("name"),
                    patient_phone=patient.get("phone"),
                    patient_id=str(patient.get("patient_id")) if patient.get("patient_id") else None,
                    booking_id=patient.get("booking_id"),
                    token=patient.get("token"),
                    booking_status=patient.get("status"),
                    booking_date=date_key
                )
    
    # لم نجد الكود
    return schemas.VerifyGoldenCodeResponse(
        status="error",
        message="الكود غير صحيح أو غير موجود"
    )


@router.get("/all_days_golden", response_model=schemas.AllDaysResponse)
def get_all_days_golden(
    clinic_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """إرجاع جميع الأيام المؤرشفة من Golden Book كقاموس days.

    الشكل:
    {
      "clinic_id": <id>,
      "days": {
         "2025-10-04": {
            "capacity_total": 5,
            "capacity_served": 3,
            "capacity_cancelled": 1,
            "patients": [...]
         },
         ...
      }
    }
    """
    rows = (
        db.query(models.GoldenBookingArchive)
        .filter(models.GoldenBookingArchive.clinic_id == clinic_id)
        .order_by(models.GoldenBookingArchive.table_date.asc())
        .all()
    )
    
    days: dict[str, dict] = {}
    for r in rows:
        try:
            patients = json.loads(r.patients_json) if r.patients_json else []
            if not isinstance(patients, list):
                patients = []
        except Exception:
            patients = []
        
        capacity_used = len([p for p in patients if isinstance(p, dict)])
        
        days[r.table_date] = {
            "capacity_total": r.capacity_total,
            "capacity_served": r.capacity_served,
            "capacity_cancelled": r.capacity_cancelled,
            "capacity_used": capacity_used,
            "status": "open",
            "patients": patients,
        }
    
    return schemas.AllDaysResponse(clinic_id=clinic_id, days=days)
