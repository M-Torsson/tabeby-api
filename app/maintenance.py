"""
App Maintenance Mode API
نظام إدارة وضع الصيانة للتطبيق
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from .database import SessionLocal
from . import models
from .doctors import require_profile_secret

router = APIRouter(prefix="/api", tags=["Maintenance"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===== Request/Response Models =====

class MaintenanceToggleRequest(BaseModel):
    """طلب تغيير حالة الصيانة"""
    server_disable: bool
    message: Optional[str] = "نعتذر عن هذا التوقف في السيرفر, لاغراض الصيانة, سوف يتم اعادة العمل خلال مدة قصيرة جدا.. شكرا لتفهمكم."


class MaintenanceStatusResponse(BaseModel):
    """رد حالة الصيانة"""
    server_disable: bool
    message: str


# ===== Maintenance Endpoints =====

@router.post("/maintenance/toggle", response_model=MaintenanceStatusResponse)
def toggle_maintenance_mode(
    payload: MaintenanceToggleRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    تفعيل/إيقاف وضع الصيانة
    
    - server_disable: true لتفعيل الصيانة (إيقاف السيرفر), false للتشغيل العادي
    - message: رسالة الصيانة التي تظهر للمستخدمين
    """
    # البحث عن سجل الصيانة (يجب أن يكون واحد فقط)
    maintenance = db.query(models.AppMaintenance).first()
    
    if not maintenance:
        # إنشاء سجل جديد إذا لم يوجد
        maintenance = models.AppMaintenance(
            is_active=payload.server_disable,
            message_ar=payload.message,
            message_en=payload.message
        )
        db.add(maintenance)
    else:
        # تحديث السجل الموجود
        maintenance.is_active = payload.server_disable
        maintenance.message_ar = payload.message
        maintenance.message_en = payload.message
    
    db.commit()
    db.refresh(maintenance)
    
    return MaintenanceStatusResponse(
        server_disable=maintenance.is_active,
        message=maintenance.message_ar or ""
    )


@router.get("/maintenance/status", response_model=MaintenanceStatusResponse)
def get_maintenance_status(
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    الحصول على حالة الصيانة الحالية
    
    يتطلب Doctor-Secret للوصول
    
    الرد دائماً:
    {
        "server_disable": false,  // true = التطبيق موقوف للصيانة
        "message": "رسالة الصيانة"
    }
    """
    maintenance = db.query(models.AppMaintenance).first()
    
    if not maintenance:
        # إذا لم يوجد سجل، نرجع حالة تشغيل عادية
        return MaintenanceStatusResponse(
            server_disable=False,
            message=""
        )
    
    return MaintenanceStatusResponse(
        server_disable=maintenance.is_active,
        message=maintenance.message_ar or ""
    )
