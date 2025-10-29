from __future__ import annotations
from datetime import datetime
from typing import Dict, List
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import SessionLocal
from . import models, schemas
from .doctors import require_profile_secret

router = APIRouter(prefix="/api", tags=["Golden Payments"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _parse_exam_date_to_month(exam_date: str) -> str:
    """
    تحويل تاريخ الفحص إلى صيغة YYYY-MM
    
    Args:
        exam_date: بصيغة DD/MM/YYYY مثل "23/10/2025"
    
    Returns:
        صيغة YYYY-MM مثل "2025-10"
    """
    try:
        # Parse DD/MM/YYYY
        dt = datetime.strptime(exam_date, "%d/%m/%Y")
        return dt.strftime("%Y-%m")
    except Exception:
        # إذا فشل التحويل، استخدم الشهر الحالي
        return datetime.now().strftime("%Y-%m")


@router.post("/golden_patient_payment", response_model=schemas.GoldenPatientPaymentResponse)
def golden_patient_payment(
    payload: schemas.GoldenPatientPaymentRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    حفظ دفعة مريض Golden Booking عند تأكيد السكرتير.
    
    يتم حفظ المريض في جدول golden_payments مع:
    - مبلغ ثابت: 1500 دينار
    - حالة الدفع: not_paid (افتراضياً)
    - الشهر: يُستخرج من exam_date
    
    Body:
    {
        "clinic_id": 4,
        "exam_date": "23/10/2025",
        "book_status": "تمت المعاينة",
        "patient_name": "عمر احمد",
        "booking_id": "G-4-20251029-P-71",
        "code": "6270"
    }
    
    يتطلب: Doctor-Secret header
    """
    # استخراج الشهر من التاريخ
    payment_month = _parse_exam_date_to_month(payload.exam_date)
    
    # التحقق إذا كان الحجز موجود مسبقاً
    existing = db.query(models.GoldenPayment).filter(
        models.GoldenPayment.booking_id == payload.booking_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "duplicate", "message": "هذا الحجز تم حفظه مسبقاً في سجل الدفعات"}}
        )
    
    # إنشاء سجل دفع جديد
    payment = models.GoldenPayment(
        clinic_id=payload.clinic_id,
        booking_id=payload.booking_id,
        patient_name=payload.patient_name,
        code=payload.code,
        exam_date=payload.exam_date,
        book_status=payload.book_status,
        amount=1500,  # ثابت
        payment_month=payment_month,
        payment_status="not_paid"  # افتراضياً
    )
    
    db.add(payment)
    db.commit()
    db.refresh(payment)
    
    return schemas.GoldenPatientPaymentResponse(
        message="تم حفظ الدفعة بنجاح",
        booking_id=payment.booking_id,
        patient_name=payment.patient_name,
        amount=payment.amount,
        payment_month=payment.payment_month,
        payment_status=payment.payment_status
    )


@router.get("/doctor_monthly_golden_payment_status")
def doctor_monthly_golden_payment_status(
    clinic_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    الحصول على سجل الدفعات الشهرية لعيادة معينة.
    
    Response:
    {
        "clinic_id": 4,
        "2025": {
            "2025-10": {
                "payment_status": "not_paid",
                "patinets_count": 2,
                "amount": 3000,
                "patients": [...]
            },
            "2025-11": {
                "payment_status": "not_paid",
                "patinets_count": 5,
                "amount": 7500,
                "patients": [...]
            }
        }
    }
    
    يتطلب: Doctor-Secret header
    """
    # جلب جميع الدفعات للعيادة
    payments = db.query(models.GoldenPayment).filter(
        models.GoldenPayment.clinic_id == clinic_id
    ).order_by(models.GoldenPayment.payment_month.asc()).all()
    
    # تجميع حسب السنة والشهر
    years_data: Dict[str, Dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {
        "payment_status": "not_paid",
        "patinets_count": 0,
        "amount": 0,
        "patients": []
    }))
    
    for payment in payments:
        year = payment.payment_month[:4]  # استخراج السنة من YYYY-MM
        month = payment.payment_month  # YYYY-MM
        
        month_data = years_data[year][month]
        month_data["patinets_count"] += 1
        month_data["amount"] += payment.amount
        month_data["patients"].append({
            "exam_date": payment.exam_date,
            "book_status": payment.book_status,
            "patient_name": payment.patient_name,
            "booking_id": payment.booking_id,
            "code": payment.code
        })
        
        # تحديث حالة الدفع (إذا كان أي مريض paid، الشهر كله paid)
        if payment.payment_status == "paid":
            month_data["payment_status"] = "paid"
    
    # تحويل defaultdict إلى dict عادي
    result = {
        "clinic_id": clinic_id,
        **{year: dict(months) for year, months in years_data.items()}
    }
    
    return result


@router.get("/doctor_annual_payment_status")
def doctor_annual_payment_status(
    clinic_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    الحصول على ملخص الدفعات السنوية لعيادة معينة.
    
    Response:
    {
        "clinic_id": 6,
        "total_paid": 13000,
        "remain_amount": 7500,
        "2025-10": {
            "amount": 3000,
            "payment_status": "paid"
        },
        "2025-11": {
            "amount": 7500,
            "payment_status": "not_paid"
        }
    }
    
    يتطلب: Doctor-Secret header
    """
    # جلب جميع الدفعات للعيادة
    payments = db.query(models.GoldenPayment).filter(
        models.GoldenPayment.clinic_id == clinic_id
    ).order_by(models.GoldenPayment.payment_month.asc()).all()
    
    # تجميع حسب الشهر
    months_summary: Dict[str, dict] = defaultdict(lambda: {
        "amount": 0,
        "payment_status": "not_paid"
    })
    
    total_paid = 0
    total_amount = 0
    
    for payment in payments:
        month = payment.payment_month
        months_summary[month]["amount"] += payment.amount
        total_amount += payment.amount
        
        # تحديث حالة الدفع
        if payment.payment_status == "paid":
            months_summary[month]["payment_status"] = "paid"
            total_paid += payment.amount
    
    remain_amount = total_amount - total_paid
    
    result = {
        "clinic_id": clinic_id,
        "total_paid": total_paid,
        "remain_amount": remain_amount,
        **dict(months_summary)
    }
    
    return result


@router.post("/update_payment_status")
def update_payment_status(
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    تحديث حالة الدفع لشهر معين.
    
    Body:
    {
        "clinic_id": 4,
        "payment_month": "2025-10",
        "payment_status": "paid"
    }
    
    يتطلب: Doctor-Secret header
    """
    clinic_id = payload.get("clinic_id")
    payment_month = payload.get("payment_month")
    payment_status = payload.get("payment_status", "paid")
    
    if not clinic_id or not payment_month:
        raise HTTPException(
            status_code=400,
            detail={"error": {"code": "bad_request", "message": "clinic_id و payment_month مطلوبان"}}
        )
    
    # تحديث جميع الدفعات في هذا الشهر
    updated_count = db.query(models.GoldenPayment).filter(
        models.GoldenPayment.clinic_id == clinic_id,
        models.GoldenPayment.payment_month == payment_month
    ).update({"payment_status": payment_status})
    
    db.commit()
    
    return {
        "message": f"تم تحديث حالة الدفع لـ {updated_count} مريض",
        "clinic_id": clinic_id,
        "payment_month": payment_month,
        "payment_status": payment_status,
        "updated_count": updated_count
    }
