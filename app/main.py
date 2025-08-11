import os
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal
from . import models, schemas
from .auth import router as auth_router
from .users import router as users_router
from .admins import router as admins_router
from .activities import router as activities_router
from fastapi.middleware.cors import CORSMiddleware

# إنشاء الجداول عند تشغيل التطبيق لأول مرة
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tabeby API")

# CORS configuration: allow configured origins and any localhost/127.0.0.1 port by default
configured_origins = os.getenv("FRONTEND_ORIGINS")
allow_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://tabeby-api.onrender.com",  # اختياري
]
if configured_origins:
    allow_origins = [o.strip() for o in configured_origins.split(",") if o.strip()]

allow_origin_regex = os.getenv(
    "FRONTEND_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1)(:\\d+)?$",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
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

# دمج مسارات التوثيق
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(admins_router)
app.include_router(activities_router)

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
