import os
from fastapi import FastAPI, Depends, HTTPException, APIRouter, Request, Response
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal
from . import models, schemas
from .auth import router as auth_router
from .users import router as users_router
from .admins import router as admins_router
from .staff_router import router as staff_rbac_router
from .activities import router as activities_router
from .departments import router as departments_router
from .doctors import router as doctors_router
from fastapi.middleware.cors import CORSMiddleware
from .firebase_init import ensure_firebase_initialized
from .doctors import _denormalize_profile, _to_ascii_digits  # reuse helpers
import json
import re
from typing import Any, Dict

# إنشاء الجداول عند تشغيل التطبيق لأول مرة (بما في ذلك جداول RBAC الجديدة)
Base.metadata.create_all(bind=engine)

# Initialize Firebase before routers
try:
    ensure_firebase_initialized()
except Exception as _e:
    # Don't crash app startup in dev if env var is missing; raise only when endpoint is called
    pass

app = FastAPI(title="Tabeby API")

# CORS configuration: allow configured origins and any localhost/127.0.0.1 port by default

# تحديث إعدادات CORS لتسمح بجميع الدومينات المطلوبة
configured_origins = os.getenv("FRONTEND_ORIGINS")
allow_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://tabeby-api.onrender.com",
    "https://tabeby.app",
    "https://www.tabeby.app",
]
if configured_origins:
    allow_origins += [o.strip() for o in configured_origins.split(",") if o.strip() and o.strip() not in allow_origins]

allow_origin_regex = os.getenv(
    "FRONTEND_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1|tabeby-api\.onrender\.com|tabeby\.app|www\.tabeby\.app)(:\\d+)?$",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # يسمح لجميع الدومينات مؤقتاً لحل مشكلة CORS
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# دالة للحصول على جلسة قاعدة البيانات
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# فحص الصحة
@app.get("/health")
def health():
    return {"status": "ok"}

# Firebase quick check route
@app.get("/_firebase_check")
def firebase_check():
    # Ensure initialization here if not already initialized
    try:
        ensure_firebase_initialized()
    except Exception as e:
        # Return safe error (no secrets) to help diagnose
        return {"ok": False, "error": str(e)}
    try:
        from firebase_admin import auth as firebase_auth  # type: ignore
        # Python Admin SDK uses max_results/page_token or iterate_all()
        sample_uid = None
        try:
            for u in firebase_auth.list_users().iterate_all():
                sample_uid = u.uid
                break
        except Exception:
            # Fallback minimal call
            page = firebase_auth.list_users()
            sample_uid = page.users[0].uid if getattr(page, 'users', []) else None
        return {"ok": True, "sample_uid": sample_uid}
    except Exception as e:
        return {"ok": False, "error": f"auth access failed: {e}"}

# إضافة مسار للحصول على عدد الموظفين بدون توكن (يجب تسجيله قبل راوتر /staff)
@app.get("/staff/count")
def get_staff_count(active_only: bool = False, db: Session = Depends(get_db)):
    """
    إرجاع عدد الموظفين من جدول Staff فقط (بدون توكن).
    - يمكن تمرير active_only=true لحصر العد على الحالة "active" فقط.
    """
    if not hasattr(models, "Staff"):
        return {"count": 0}
    try:
        q = db.query(models.Staff)
        # إن وُجد عمود status وطلب المستخدم حصر العد على النشطين فقط
        if active_only and hasattr(models.Staff, "status"):
            q = q.filter(getattr(models.Staff, "status") == "active")
        return {"count": q.count()}
    except Exception:
        # في حال وجود مشكلة في ORM، أعد 0 بدل الانهيار
        return {"count": 0}

# دمج مسارات التوثيق
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(admins_router)
app.include_router(staff_rbac_router)
app.include_router(activities_router)
app.include_router(departments_router)
app.include_router(doctors_router)

# راوتر توافق لطلبـات قديمة تبدأ بـ /backend (مخفى عن الوثائق)
from .auth import get_current_admin
from sqlalchemy.orm import Session, load_only
from .database import SessionLocal
from . import models
backend_router = APIRouter(prefix="/backend", include_in_schema=False)
backend_router.include_router(auth_router)
backend_router.include_router(users_router)
backend_router.include_router(admins_router)
backend_router.include_router(staff_rbac_router)
backend_router.include_router(activities_router)
backend_router.include_router(departments_router)
backend_router.include_router(doctors_router)

# /backend/me  => /users/me
def _light_admin(admin_id: int):
    db = SessionLocal()
    try:
        a = db.query(models.Admin).options(load_only(models.Admin.id, models.Admin.name, models.Admin.email, models.Admin.is_active, models.Admin.is_superuser)).filter_by(id=admin_id).first()
        if not a:
            return None
        return {
            "id": a.id,
            "name": a.name,
            "email": a.email,
            "is_active": getattr(a, 'is_active', True),
            "is_superuser": getattr(a, 'is_superuser', False),
            "two_factor_enabled": False,
        }
    finally:
        db.close()

@backend_router.get("/me")
def backend_me(current_admin: models.Admin = Depends(get_current_admin)):
    return _light_admin(current_admin.id)

# /backend/auth/me (بعض الواجهات تتوقعه)
@backend_router.get("/auth/me")
def backend_auth_me(current_admin: models.Admin = Depends(get_current_admin)):
    return _light_admin(current_admin.id)

# /backend/users/profile => تعيد نفس /users/me
@backend_router.get("/users/profile")
def backend_users_profile(current_admin: models.Admin = Depends(get_current_admin)):
    return _light_admin(current_admin.id)

app.include_router(backend_router)

# دعم مسار قديم /backend/admins/list لو أن الفرونت ما زال يستخدمه (يجب إزالته لاحقاً)
from fastapi import APIRouter
from .auth import get_current_admin  # استدعاء مباشر للدالة
legacy_router = APIRouter(include_in_schema=False)

@legacy_router.get("/backend/admins/list")
def legacy_backend_admins_list(db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    from .admins import list_admins
    return list_admins(db=db, current_admin=current_admin)

app.include_router(legacy_router)

# مسار الجذر لعرض رسالة بسيطة أو تحويل إلى الوثائق
@app.get("/")
def root():
    return {"message": "Tabeby API is running", "docs": "/docs", "health": "/health"}

# إضافة مريض جديد
@app.post("/patients", response_model=schemas.PatientOut)
def create_patient(payload: schemas.PatientCreate, db: Session = Depends(get_db)):
    exists = db.query(models.Patient).filter_by(email=payload.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email already exists")
    patient = models.Patient(name=payload.name, email=payload.email)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient

# عرض جميع المرضى
@app.get("/patients", response_model=list[schemas.PatientOut])
def list_patients(db: Session = Depends(get_db)):
    return db.query(models.Patient).all()

# نعيد محتوى ملف JSON كما هو تماماً بدون أي تعديل
RAW_DOCTOR_PROFILE_JSON = r"""{
    "general_info" : {
        "create_date" : "٢٠٢٥-٠٨-٢٤ ٠٣:٠٧ م",
        "profile_image_URL" : "http:\/\/",
        "about_doctor_bio" : "أنا ما أعرف كيف أتعامل معاه و أنا من وجهة نظره ما أعرف كيف أتصرف معاه بس أنا مب عارفه كيف أتصرف مع الناس ",
        "doctor_phone_number" : "07701234569",
        "gender" : "رجل",
        "clinic_states" : "كركوك",
        "doctor_name" : "عمر حازم",
        "email_address" : "Fgfftg@gmail.com",
        "experience_years" : "٥",
        "accountStatus" : false,
        "examination_fees" : "٢٠٠٠٠",
        "number_patients_treated" : "٨٠٠٠",
        "license_number" : "١١٥٢٤٥",
        "clinic_name" : "عيادة معلش يا جميل",
        "clinic_address" : "ما هي احتياطات استخدام زيت الزيتون في علاج التهاب المفاصل ",
        "receiving_patients" : "٢٠"
    },
    "clinck_days" : {
        "to" : "الجمعة",
        "from" : "السبت"
    },
    "specializations" : [
        "نسائية وتوليد \/ رعاية حوامل",
        "الغدد الصماء",
        "طب الأسنان"
    ],
    "clinic_phone_number" : {
        "phone_3" : "",
        "phone_1" : "٠٧٧٠١٢٣٥٧٨٦٥",
        "phone_2" : "٠٧٨٠١٢٢٥٤٧٨٨"
    },
    "clinic_location" : {
        "latitude" : "30.058236133217274",
        "place_name" : "12588, الشيخ زايد, مصر",
        "longitude" : "30.963241597456566"
    },
    "certifications" : [
        "MSc",
        "BSN",
        "DO"
    ],
    "clinck_hours" : {
        "to" : "10:00 مساءا",
        "from" : "1:00 مساءا"
    },
    "clinic_waiting_time" : {
        "id" : 3,
        "name" : "15 دقيقة"
    }
}"""

# تحويل شكل الحقل clinic_waiting_time من الشكل القديم { value: "..." }
# إلى الشكل الجديد { id: 3, name: "15 دقيقة" }
def _normalize_clinic_waiting_time(profile_obj: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if not isinstance(profile_obj, dict):
            return profile_obj
        cwt = profile_obj.get("clinic_waiting_time")
        if isinstance(cwt, dict):
            # إن كان بالشكل القديم يحتوي value فقط، استبدله بالشكل الجديد المطلوب
            if "value" in cwt and ("id" not in cwt and "name" not in cwt):
                profile_obj["clinic_waiting_time"] = {"id": 3, "name": "15 دقيقة"}
        return profile_obj
    except Exception:
        return profile_obj

@app.get("/doctor/profile")
@app.get("/doctor/profile.json")
def get_doctor_profile_raw():
    """
    يُعيد حالة نجاح/فشل للبروفايل المخزّن من جدول DoctorProfile (slug=default).
    في حال عدم وجود صف سيتم إنشاؤه بالقيمة الافتراضية.
    """
    db = SessionLocal()
    try:
        row = db.query(models.DoctorProfile).filter_by(slug="default").first()
        if not row:
            row = models.DoctorProfile(slug="default", raw_json=RAW_DOCTOR_PROFILE_JSON)
            db.add(row)
            db.commit()
        # تحقق من صحة JSON المخزّن
        try:
            json.loads(row.raw_json) if row.raw_json else {}
            return {"status": "success", "message": "Profile exists and valid"}
        except Exception:
            return {"status": "fail", "message": "Profile exists but invalid"}
    except Exception:
        return {"status": "fail", "message": "Failed to access profile"}
    finally:
        db.close()
    
@app.post("/doctor/profile")
@app.post("/doctor/profile.json")
async def post_doctor_profile_raw(request: Request):
    raw = await request.body()
    text = raw.decode("utf-8", errors="replace")

    # إذا كان الجسم بالشكل الجديد { phone, json_profile } نُنشئ طبيباً ونُرجِع العقد الجديد
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None

    if isinstance(parsed, dict) and ("json_profile" in parsed or "phone" in parsed or "user_server_id" in parsed):
        db = SessionLocal()
        try:
            # 1) تحضير الملف الشخصي
            prof_val = parsed.get("json_profile")
            if isinstance(prof_val, str):
                try:
                    prof = json.loads(prof_val)
                except Exception:
                    prof = {}
                # طبّق التطبيع ثم أعد التسلسل
                prof = _normalize_clinic_waiting_time(prof)
                prof_raw = json.dumps(prof, ensure_ascii=False)
            elif isinstance(prof_val, dict):
                prof = _normalize_clinic_waiting_time(prof_val)
                prof_raw = json.dumps(prof, ensure_ascii=False)
            else:
                prof = {}
                prof_raw = "{}"

            # 2) الهاتف بصيغة E.164 (يمكن تجاوزه إن كان مرتبطًا بحساب مستخدم موجود)
            phone_in = parsed.get("phone")
            phone_ascii = _to_ascii_digits(str(phone_in)) if phone_in is not None else None
            phone_ascii = phone_ascii.strip() if isinstance(phone_ascii, str) else None
            e164_pat = re.compile(r"^\+[1-9]\d{6,14}$")

            # لو وصل user_server_id، اجلب حساب المستخدم لاستنتاج الهاتف
            acct = None
            user_server_id = parsed.get("user_server_id")
            if user_server_id is not None:
                try:
                    uid_int = int(str(user_server_id))
                    acct = db.query(models.UserAccount).filter_by(id=uid_int).first()
                except Exception:
                    acct = None
            if acct and acct.phone_number:
                phone_ascii = acct.phone_number

            if not phone_ascii or not e164_pat.match(phone_ascii):
                return Response(content=json.dumps({"error": {"code": "bad_request", "message": "phone must be E.164 like +46765588441 or provide valid user_server_id"}}, ensure_ascii=False), media_type="application/json", status_code=400)

            # 3) استخراج قيم من الملف الشخصي وتحديث الهاتف بما أُرسِل
            den = _denormalize_profile(prof)
            den["phone"] = phone_ascii

            # 4) إنشاء الطبيب
            row = models.Doctor(
                name=den.get("name") or "Doctor",
                email=den.get("email"),
                phone=den.get("phone"),
                experience_years=den.get("experience_years"),
                patients_count=den.get("patients_count"),
                status=den.get("status") or "active",
                specialty=den.get("specialty"),
                clinic_state=den.get("clinic_state"),
                profile_json=prof_raw,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            # اربط حساب المستخدم (إن وجد) بهذا الطبيب
            if acct and not acct.doctor_id:
                acct.doctor_id = row.id
                db.commit()
            return {"doctor_id": row.id, "phone_verification": "pending", "profile": prof}
        finally:
            db.close()

    # سلوك التوافق القديم: خزّن النص الخام كما هو في جدول DoctorProfile (slug=default)
    db = SessionLocal()
    try:
        row = db.query(models.DoctorProfile).filter_by(slug="default").first()
        # حاول تحويل النص إلى JSON وتطبيق التطبيع إن أمكن
        normalized_text = text
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                obj = _normalize_clinic_waiting_time(obj)
                normalized_text = json.dumps(obj, ensure_ascii=False)
        except Exception:
            pass
        if not row:
            row = models.DoctorProfile(slug="default", raw_json=normalized_text)
            db.add(row)
        else:
            row.raw_json = normalized_text
        db.commit()
        # إن كان النص JSON صالحًا، أعده أيضًا للعميل
        try:
            resp_obj = json.loads(normalized_text)
        except Exception:
            resp_obj = {"message": "Done"}
        return {"message": "Done", "profile": resp_obj}
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return Response(content=json.dumps({"message": "Failed"}, ensure_ascii=False), media_type="application/json", status_code=500)
    finally:
        db.close()

# جلب البروفايل المخزّن لطبيب عبر المعرّف كما هو (بدون أي تعديل/التفاف)
@app.get("/doctor/profile/{doctor_id}")
@app.get("/doctor/profile.json/{doctor_id}")
def get_doctor_profile_by_id(doctor_id: int):
    db = SessionLocal()
    try:
        r = db.query(models.Doctor).filter_by(id=doctor_id).first()
        if not r:
            return Response(content=json.dumps({"error": {"code": "not_found", "message": "Doctor not found"}}, ensure_ascii=False), media_type="application/json", status_code=404)
        try:
            obj = json.loads(r.profile_json) if r.profile_json else {}
        except Exception:
            obj = {}
        return obj
    finally:
        db.close()

# تحقق بعد تسجيل الدخول بالهاتف باستخدام Firebase ID Token
@app.post("/auth/after-phone-login")
def after_phone_login(request: Request):
    # استخراج التوكن من الهيدر Authorization: Bearer <ID_TOKEN>
    authz = request.headers.get("authorization") or request.headers.get("Authorization")
    if not authz or not authz.lower().startswith("bearer "):
        return Response(content=json.dumps({"error": {"code": "unauthorized", "message": "Missing Bearer token"}}), media_type="application/json", status_code=401)
    id_token = authz.split(" ", 1)[1].strip()

    try:
        ensure_firebase_initialized()
        from firebase_admin import auth as firebase_auth  # type: ignore
        decoded = firebase_auth.verify_id_token(id_token)
        uid = decoded.get("uid")
        phone = decoded.get("phone_number")
        # إن لم يوجد phone_number داخل التوكن، اجلب المستخدم للتأكد
        if not phone and uid:
            try:
                u = firebase_auth.get_user(uid)
                phone = getattr(u, "phone_number", None)
            except Exception:
                phone = None
    except Exception as e:
        return Response(content=json.dumps({"error": {"code": "unauthorized", "message": f"Token invalid: {str(e)}"}}), media_type="application/json", status_code=401)

    if not phone:
        return Response(content=json.dumps({"error": {"code": "bad_request", "message": "No phone_number in token"}}), media_type="application/json", status_code=400)

    # طبّق تحويل الأرقام والتأكد من E.164
    phone_ascii = _to_ascii_digits(str(phone)).strip()
    if not re.match(r"^\+[1-9]\d{6,14}$", phone_ascii):
        return Response(content=json.dumps({"error": {"code": "bad_request", "message": "phone_number not E.164"}}), media_type="application/json", status_code=400)

    # ابحث عن الطبيب حسب رقم الهاتف
    db = SessionLocal()
    try:
        # أولاً: لو يوجد حساب مستخدم لهذا الهاتف، استخدم الربط المباشر
        acct = db.query(models.UserAccount).filter(models.UserAccount.phone_number == phone_ascii).first()
        if acct and acct.doctor_id:
            doc = db.query(models.Doctor).filter(models.Doctor.id == acct.doctor_id).first()
        else:
            doc = db.query(models.Doctor).filter(models.Doctor.phone == phone_ascii).order_by(models.Doctor.id.desc()).first()
        if not doc:
            return Response(content=json.dumps({"error": {"code": "not_found", "message": "Doctor not found for this phone"}}), media_type="application/json", status_code=404)
        # إن كان لدينا حساب مستخدم ولم يُربط بعد، اربطه الآن
        if acct and not acct.doctor_id:
            acct.doctor_id = doc.id
            db.commit()
        return {"doctor_id": doc.id, "status": "phone_verified", "phone": phone_ascii}
    finally:
        db.close()

# تسجيل مستخدم عام (مريض/سكرتير/دكتور) وإرجاع user_server_id
@app.post("/auth/register")
async def register_user(request: Request):
    try:
        body = await request.json()
        assert isinstance(body, dict)
    except Exception:
        return Response(content=json.dumps({"error": {"code": "bad_request", "message": "Invalid JSON"}}), media_type="application/json", status_code=400)

    user_uid = (body.get("user_uid") or "").strip() or None
    user_role = (body.get("user_role") or "").strip()
    phone = (body.get("phone_number") or "").strip()
    from .doctors import _to_ascii_digits as _digits
    phone = _digits(phone)

    if user_role not in {"patient", "secretary", "doctor"}:
        return Response(content=json.dumps({"error": {"code": "bad_request", "message": "user_role must be patient|secretary|doctor"}}), media_type="application/json", status_code=400)
    if not re.match(r"^\+[1-9]\d{6,14}$", phone or ""):
        return Response(content=json.dumps({"error": {"code": "bad_request", "message": "phone_number must be E.164"}}), media_type="application/json", status_code=400)

    db = SessionLocal()
    try:
        # unique على رقم الهاتف؛ إن كان موجودًا أعده
        existing = db.query(models.UserAccount).filter(models.UserAccount.phone_number == phone).first()
        if existing:
            return {"message": "ok", "user_server_id": existing.id, "user_role": existing.user_role}
        row = models.UserAccount(user_uid=user_uid, user_role=user_role, phone_number=phone)
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"message": "database created successfuly", "user_server_id": row.id, "user_role": row.user_role}
    finally:
        db.close()

# إرجاع قائمة الأرقام لكل دور
@app.get("/auth/phones")
def list_phones_by_role(role: str):
    if role not in {"patient", "secretary", "doctor"}:
        return Response(content=json.dumps({"error": {"code": "bad_request", "message": "role must be patient|secretary|doctor"}}), media_type="application/json", status_code=400)
    db = SessionLocal()
    try:
        rows = (
            db.query(models.UserAccount)
            .filter(models.UserAccount.user_role == role)
            .order_by(models.UserAccount.id.asc())
            .all()
        )
        return {
            "items": [
                {
                    "user_server_id": r.id,
                    "phone_number": r.phone_number,
                    "user_uid": r.user_uid,
                    "user_role": r.user_role,
                }
                for r in rows
            ]
        }
    finally:
        db.close()

# جلب بروفايل دكتور بواسطة user_server_id
@app.get("/doctor/profile/by-user/{user_server_id}")
def get_doctor_by_user(user_server_id: int):
    db = SessionLocal()
    try:
        acct = db.query(models.UserAccount).filter_by(id=user_server_id).first()
        if not acct or not acct.doctor_id:
            return Response(content=json.dumps({"error": {"code": "not_found", "message": "No doctor mapped to this user"}}), media_type="application/json", status_code=404)
        doc = db.query(models.Doctor).filter_by(id=acct.doctor_id).first()
        if not doc:
            return Response(content=json.dumps({"error": {"code": "not_found", "message": "Doctor not found"}}), media_type="application/json", status_code=404)
        return {"id": doc.id, "name": doc.name, "email": doc.email, "phone": doc.phone, "specialty": doc.specialty, "status": doc.status}
    finally:
        db.close()

# انتهى