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
from fastapi.middleware.cors import CORSMiddleware

# إنشاء الجداول عند تشغيل التطبيق لأول مرة (بما في ذلك جداول RBAC الجديدة)
Base.metadata.create_all(bind=engine)

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
        "value" : "من ٢٥ الى ٣٠ دقيقة"
    }
}"""

@app.get("/doctor/profile.json")
def get_doctor_profile_raw():
        return Response(content=RAW_DOCTOR_PROFILE_JSON, media_type="application/json")
    
@app.post("/doctor/profile.json")
async def post_doctor_profile_raw(request: Request):
    body = await request.body()
    return Response(content=body, media_type="application/json")

# انتهى