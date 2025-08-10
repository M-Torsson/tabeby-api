from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import Base, engine, SessionLocal
from . import models, schemas
from .auth import router as auth_router

# إنشاء الجداول عند تشغيل التطبيق لأول مرة
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tabeby API")

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
