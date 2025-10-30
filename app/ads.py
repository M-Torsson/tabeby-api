from __future__ import annotations
import json
import uuid
import base64
import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from PIL import Image
import requests

from .database import SessionLocal
from . import models
from .dependencies import require_profile_secret

router = APIRouter(prefix="/api", tags=["Ads"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Arabic to ASCII digits map
_AR2EN = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def _to_ascii_digits(v: Optional[str | int | float]) -> Optional[str]:
    if v is None:
        return None
    return str(v).translate(_AR2EN)


def _parse_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in {"true", "1", "yes", "y", "صح"}:
        return True
    if s in {"false", "0", "no", "n", "خطأ"}:
        return False
    return default


def _normalize_ad_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    # ensure clinic_id number
    cid_raw = body.get("clinic_id")
    cid = _to_ascii_digits(cid_raw)
    try:
        clinic_id = int(cid) if cid is not None else None
    except Exception:
        clinic_id = None

    if clinic_id is None:
        raise HTTPException(status_code=400, detail={
            "error": {"code": "bad_request", "message": "clinic_id must be provided and numeric"}
        })

    # normalize price to int if present
    price_raw = body.get("ad_price")
    price_val = None
    if price_raw is not None and price_raw != "":
        s = _to_ascii_digits(price_raw) or ""
        s_digits = "".join(ch for ch in s if ch.isdigit())
        price_val = int(s_digits) if s_digits else None

    # normalize phone
    phone_raw = body.get("ad_phonenumber")
    phone_ascii = _to_ascii_digits(phone_raw) if phone_raw is not None else None

    # normalize discount
    discount_raw = body.get("ad_discount")
    discount_ascii = _to_ascii_digits(discount_raw) if discount_raw is not None else None

    status_raw = body.get("ad_status")
    status_bool = _parse_bool(status_raw, default=False)

    out = dict(body)
    out["clinic_id"] = clinic_id
    if price_raw is not None:
        out["ad_price"] = price_val
    if phone_ascii is not None:
        out["ad_phonenumber"] = phone_ascii
    if discount_ascii is not None:
        out["ad_discount"] = discount_ascii
    out["ad_status"] = status_bool
    return out


@router.post("/ads")
async def create_ad(request: Request, db: Session = Depends(get_db)):
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError
    except Exception:
        return JSONResponse(status_code=400, content={
            "error": {"code": "bad_request", "message": "Invalid JSON body"}
        })

    try:
        normalized = _normalize_ad_payload(body)
    except HTTPException as he:
        # pass-through
        raise he
    except Exception:
        return JSONResponse(status_code=400, content={
            "error": {"code": "bad_request", "message": "Invalid data"}
        })

    ad = models.Ad(
        clinic_id=normalized["clinic_id"],
        payload_json=json.dumps(normalized, ensure_ascii=False),
        ad_status=bool(normalized.get("ad_status", False)),
    )
    db.add(ad)
    db.commit()
    db.refresh(ad)

    return {
        "message": "success",
        "ad_id": ad.id,
        "clinic_id": ad.clinic_id,
        "data": normalized,
    }


@router.get("/ads/{ad_id}")
def get_ad(ad_id: int, db: Session = Depends(get_db)):
    ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not ad:
        return JSONResponse(status_code=404, content={"error": {"code": "not_found", "message": "Ad not found"}})
    try:
        data = json.loads(ad.payload_json) if ad.payload_json else {}
    except Exception:
        data = {}
    return {
        "id": ad.id,
        "clinic_id": ad.clinic_id,
        "ad_status": ad.ad_status,
        "created_at": ad.created_at.isoformat() if ad.created_at else None,
        "data": data,
    }


@router.get("/ads/by-clinic/{clinic_id}")
def list_ads_by_clinic(clinic_id: int, db: Session = Depends(get_db)):
    ads = (
        db.query(models.Ad)
        .filter(models.Ad.clinic_id == clinic_id)
        .order_by(models.Ad.id.desc())
        .all()
    )
    result: List[Dict[str, Any]] = []
    for ad in ads:
        try:
            data = json.loads(ad.payload_json) if ad.payload_json else {}
        except Exception:
            data = {}
        result.append(
            {
                "id": ad.id,
                "clinic_id": ad.clinic_id,
                "ad_status": ad.ad_status,
                "created_at": ad.created_at.isoformat() if ad.created_at else None,
                "data": data,
            }
        )
    return {"items": result, "count": len(result)}


# ==================== NEW AD ENDPOINTS ====================

def _validate_image_dimensions_and_size(image_url: str) -> tuple[bool, str | None]:
    """
    التحقق من أبعاد وحجم الصورة.
    ⚠️ هذه الدالة مُعطّلة حالياً - لا تُستخدم في /create_clinic_ad (للدكتور في التطبيق)
    يمكن استخدامها في endpoint الداشبورد إذا لزم الأمر.
    
    Returns:
        (True, None) إذا كانت الصورة صالحة
        (False, error_message) إذا كانت الصورة غير صالحة
    """
    try:
        # تحميل الصورة من URL مع timeout قصير
        response = requests.get(image_url, timeout=10, stream=True, allow_redirects=True)
        if response.status_code != 200:
            return False, f"فشل تحميل الصورة (HTTP {response.status_code})"
        
        # قراءة محتوى الصورة مع حد أقصى 2MB
        image_data = b''
        total_size = 0
        max_size = 2 * 1024 * 1024  # 2MB
        
        for chunk in response.iter_content(chunk_size=8192):
            total_size += len(chunk)
            if total_size > max_size:
                return False, "حجم الصورة يجب أن يكون أقل من 2 ميجابايت"
            image_data += chunk
        
        # فتح الصورة باستخدام PIL
        image = Image.open(io.BytesIO(image_data))
        width, height = image.size
        
        # التحقق من الأبعاد (يجب أن تكون بالضبط 500x250)
        if width != 500 or height != 250:
            return False, f"أبعاد الصورة يجب أن تكون 500x250 بالضبط. الأبعاد الحالية: {width}x{height}"
        
        return True, None
        
    except requests.exceptions.Timeout:
        return False, "انتهت مهلة الاتصال بالصورة"
    except requests.exceptions.RequestException as e:
        return False, f"فشل الاتصال بالصورة: {str(e)}"
    except Exception as e:
        return False, f"خطأ في معالجة الصورة: {str(e)}"


@router.post("/create_clinic_ad")
async def create_clinic_ad(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    إنشاء إعلان عيادة جديد.
    
    ⚠️ ملاحظة: الـ URL الكامل هو /api/create_clinic_ad
    
    Body مطلوب:
    {
        "request_date": "22/10/2025",
        "clinic_name": "عيادة الأسنان",
        "ad_subtitle": "عيادة متخصصة في كل شيء",
        "ad_description": "عرض خاص",
        "ad_phonenumber": "٠١٠١٢٣٤٥٦٧٨",
        "ad_state": "القاهرة",
        "ad_discount": "٢٠",
        "ad_price": "١٠٠",
        "ad_address": "الحي الاول",
        "team_message": "رسالة الفريق",
        "ad_image_url": "https://...",
        "clinic_id": "7",
        "ad_status": "active"
    }
    
    متطلبات الصورة:
    - الأبعاد: 500x250 بالضبط
    - الحجم: أقل من 2MB
    
    Response:
    {
        "ad_ID": "234333_rert34_rre5334",
        "ad_image": "http://ww.image",
        "ad_state": "كركوك",
        "clinic_id": 6,
        "ad_status": true,
        "expired_date": "23/10/2025"
    }
    
    يتطلب: Doctor-Secret header
    """
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError("Invalid JSON")
    except Exception as e:
        print(f"[CREATE_AD] JSON parsing error: {e}")
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "bad_request", "message": "Invalid JSON body"}}
        )
    
    # التحقق من الحقول المطلوبة
    required_fields = ["clinic_id", "ad_image_url", "ad_state"]
    for field in required_fields:
        if field not in body or not body[field]:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "bad_request", "message": f"{field} مطلوب"}}
            )
    
    # لا نقوم بالتحقق من أبعاد الصورة للدكتور في التطبيق
    # التحقق يكون فقط في الداشبورد
    image_url = body.get("ad_image_url")
    
    # تحويل clinic_id إلى رقم
    try:
        clinic_id = int(_to_ascii_digits(body["clinic_id"]))
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "bad_request", "message": "clinic_id يجب أن يكون رقماً"}}
        )
    
    # توليد ad_ID فريد
    ad_id = f"{clinic_id}_{uuid.uuid4().hex[:8]}_{int(datetime.now().timestamp())}"
    
    # تحويل الأرقام العربية
    phone = _to_ascii_digits(body.get("ad_phonenumber", ""))
    price = _to_ascii_digits(body.get("ad_price", ""))
    discount = _to_ascii_digits(body.get("ad_discount", ""))
    
    # معالجة ad_status - نحفظه false دائماً حتى يتم التفعيل
    ad_status_input = body.get("ad_status", "false")
    ad_status = False  # دائماً نبدأ بـ false
    
    # expired_date يُحسب عند التفعيل، لكن نضع placeholder في Response
    expired_date_str = "سيُحدد عند التفعيل"
    
    # بناء الـ payload الكامل للحفظ في قاعدة البيانات
    ad_data = {
        "ad_ID": ad_id,
        "request_date": body.get("request_date", datetime.now().strftime("%d/%m/%Y")),
        "clinic_name": body.get("clinic_name", ""),
        "ad_subtitle": body.get("ad_subtitle", ""),
        "ad_description": body.get("ad_description", ""),
        "ad_address": body.get("ad_address", ""),
        "ad_phonenumber": phone,
        "ad_state": body.get("ad_state"),
        "ad_discount": discount,
        "ad_price": price,
        "team_message": body.get("team_message", ""),
        "ad_image_url": image_url,
        "clinic_id": clinic_id,
        "ad_status": ad_status,
        "expired_date": expired_date_str
    }
    
    # حفظ في قاعدة البيانات
    try:
        ad = models.Ad(
            clinic_id=clinic_id,
            payload_json=json.dumps(ad_data, ensure_ascii=False),
            ad_status=ad_status,
        )
        db.add(ad)
        db.commit()
        db.refresh(ad)
        
        print(f"[CREATE_AD] ✅ Ad created successfully: {ad_id}")
        
    except Exception as e:
        print(f"[CREATE_AD] Database error: {e}")
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "server_error", "message": f"خطأ في حفظ الإعلان: {str(e)}"}}
        )
    
    # Response بالصيغة المطلوبة فقط
    return {
        "ad_ID": ad_id,
        "ad_image": image_url,
        "ad_state": body.get("ad_state"),
        "clinic_id": clinic_id,
        "ad_status": ad_status,
        "expired_date": expired_date_str
    }


@router.get("/get_ad_image")
def get_ad_image(
    ad_ID: Optional[str] = None,
    clinic_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    الحصول على بيانات الإعلان بالصيغة المطلوبة.
    
    Query Parameters:
    - ad_ID: معرّف الإعلان (اختياري)
    - clinic_id: معرّف العيادة (اختياري)
    
    Response:
    {
        "ad_ID": "234333_rert34_rre5334",
        "ad_image": "http://ww.image",
        "ad_state": "كركوك",
        "clinic_id": 6,
        "ad_status": true,
        "expired_date": "23/10/2025"
    }
    
    يتطلب: Doctor-Secret header
    """
    query = db.query(models.Ad)
    
    if ad_ID:
        # البحث بـ ad_ID داخل الـ payload
        ads = query.all()
        for ad in ads:
            try:
                data = json.loads(ad.payload_json) if ad.payload_json else {}
                if data.get("ad_ID") == ad_ID:
                    return {
                        "ad_ID": data.get("ad_ID"),
                        "ad_image": data.get("ad_image_url"),
                        "ad_state": data.get("ad_state"),
                        "clinic_id": data.get("clinic_id"),
                        "ad_status": data.get("ad_status", False),
                        "expired_date": data.get("expired_date")
                    }
            except Exception:
                continue
        
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Ad not found"}}
        )
    
    elif clinic_id:
        # البحث بـ clinic_id - إرجاع جميع الإعلانات للعيادة
        ads = query.filter(models.Ad.clinic_id == clinic_id).order_by(models.Ad.id.desc()).all()
        result = []
        
        for ad in ads:
            try:
                data = json.loads(ad.payload_json) if ad.payload_json else {}
                result.append({
                    "ad_ID": data.get("ad_ID"),
                    "ad_image": data.get("ad_image_url"),
                    "ad_state": data.get("ad_state"),
                    "clinic_id": data.get("clinic_id"),
                    "ad_status": data.get("ad_status", False),
                    "expired_date": data.get("expired_date")
                })
            except Exception:
                continue
        
        return {"items": result, "count": len(result)}
    
    else:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "bad_request", "message": "Either ad_ID or clinic_id is required"}}
        )


@router.get("/get_all_ads")
def get_all_ads(
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    الحصول على جميع الإعلانات النشطة.
    
    Response: قائمة بجميع الإعلانات بالصيغة المطلوبة
    
    يتطلب: Doctor-Secret header
    """
    ads = db.query(models.Ad).filter(models.Ad.ad_status == True).order_by(models.Ad.id.desc()).all()
    result = []
    
    for ad in ads:
        try:
            data = json.loads(ad.payload_json) if ad.payload_json else {}
            result.append({
                "ad_ID": data.get("ad_ID"),
                "ad_image": data.get("ad_image_url"),
                "ad_state": data.get("ad_state"),
                "clinic_id": data.get("clinic_id"),
                "ad_status": data.get("ad_status", False),
                "expired_date": data.get("expired_date")
            })
        except Exception:
            continue
    
    return {"items": result, "count": len(result)}


@router.get("/clinic_ads_all")
def get_all_clinic_ads_including_inactive(
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    الحصول على جميع الإعلانات (المفعّلة وغير المفعّلة) - للداشبورد
    
    Response: جميع الإعلانات بكامل التفاصيل + doctor_name
    
    يتطلب: Doctor-Secret header
    """
    # جلب جميع الإعلانات
    ads = db.query(models.Ad).order_by(models.Ad.id.desc()).all()
    result = []
    
    for ad in ads:
        try:
            data = json.loads(ad.payload_json) if ad.payload_json else {}
            
            # جلب اسم الدكتور من clinic_id
            clinic_id = data.get("clinic_id")
            doctor_name = None
            
            if clinic_id:
                doctor = db.query(models.Doctor).filter(models.Doctor.id == clinic_id).first()
                if doctor:
                    doctor_name = doctor.name
            
            # إضافة اسم الدكتور
            data["doctor_name"] = doctor_name
            
            result.append(data)
        except Exception:
            continue
    
    return {"items": result, "count": len(result)}


@router.get("/clinic_ads")
def get_all_clinic_ads(
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    الحصول على الإعلانات النشطة فقط مع كامل البيانات + اسم الدكتور
    
    Response: الإعلانات النشطة (ad_status = true) فقط بكامل التفاصيل + doctor_name
    
    يتطلب: Doctor-Secret header
    """
    # فلترة الإعلانات النشطة فقط
    ads = db.query(models.Ad).filter(models.Ad.ad_status == True).order_by(models.Ad.id.desc()).all()
    result = []
    
    for ad in ads:
        try:
            data = json.loads(ad.payload_json) if ad.payload_json else {}
            
            # التأكد من أن ad_status في البيانات أيضاً true
            if not data.get("ad_status", False):
                continue
            
            # جلب اسم الدكتور من clinic_id
            clinic_id = data.get("clinic_id")
            doctor_name = None
            
            if clinic_id:
                doctor = db.query(models.Doctor).filter(models.Doctor.id == clinic_id).first()
                if doctor:
                    doctor_name = doctor.name
            
            # إضافة اسم الدكتور والحقول المهمة للبيانات المرجعة
            data["doctor_name"] = doctor_name
            data["ad_phonenumber"] = data.get("ad_phonenumber", "")
            data["ad_subtitle"] = data.get("ad_subtitle", "")
            data["ad_discount"] = data.get("ad_discount", "")
            
            result.append(data)
        except Exception:
            continue
    
    return {"items": result, "count": len(result)}


@router.post("/toggle_ad_status")
def toggle_ad_status(
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    تغيير حالة الإعلان من active إلى inactive أو العكس
    
    Body:
    {
        "ad_ID": "234333_rert34_rre5334"
    }
    
    يتطلب: Doctor-Secret header
    """
    ad_id = payload.get("ad_ID")
    if not ad_id:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "bad_request", "message": "ad_ID is required"}}
        )
    
    # البحث عن الإعلان
    ads = db.query(models.Ad).all()
    
    for ad in ads:
        try:
            data = json.loads(ad.payload_json) if ad.payload_json else {}
            if data.get("ad_ID") == ad_id:
                # عكس الحالة
                current_status = data.get("ad_status", False)
                new_status = not current_status
                
                # تحديث البيانات
                data["ad_status"] = new_status
                
                # إذا تم تفعيل الإعلان، أضف activated_at و expired_date (24 ساعة)
                if new_status and not current_status:
                    from datetime import datetime, timedelta
                    activated_at = datetime.utcnow()
                    expired_date = activated_at + timedelta(hours=24)
                    
                    data["activated_at"] = activated_at.isoformat() + "Z"
                    data["expired_date"] = expired_date.strftime("%d/%m/%Y %H:%M")
                
                ad.payload_json = json.dumps(data, ensure_ascii=False)
                ad.ad_status = new_status
                
                db.add(ad)
                db.commit()
                db.refresh(ad)
                
                return {
                    "message": "تم تغيير حالة الإعلان بنجاح",
                    "ad_ID": ad_id,
                    "old_status": current_status,
                    "new_status": new_status
                }
        except Exception:
            continue
    
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "not_found", "message": "Ad not found"}}
    )


@router.post("/delete_ad")
def delete_ad(
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    حذف الإعلان نهائياً من قاعدة البيانات
    
    Body:
    {
        "ad_ID": "234333_rert34_rre5334"
    }
    
    يتطلب: Doctor-Secret header
    """
    ad_id = payload.get("ad_ID")
    if not ad_id:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "bad_request", "message": "ad_ID is required"}}
        )
    
    # البحث عن الإعلان
    ads = db.query(models.Ad).all()
    
    for ad in ads:
        try:
            data = json.loads(ad.payload_json) if ad.payload_json else {}
            if data.get("ad_ID") == ad_id:
                # حذف الإعلان نهائياً
                db.delete(ad)
                db.commit()
                
                return {
                    "message": "تم حذف الإعلان بنجاح",
                    "ad_ID": ad_id,
                    "deleted": True
                }
        except Exception:
            continue
    
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "not_found", "message": "Ad not found"}}
    )


@router.post("/update_ad_with_image")
async def update_ad_with_image(
    ad_ID: str = Form(...),
    ad_image_url: Optional[str] = Form(None),
    image: UploadFile = File(None),
    clinic_name: Optional[str] = Form(None),
    ad_subtitle: Optional[str] = Form(None),
    ad_description: Optional[str] = Form(None),
    ad_phonenumber: Optional[str] = Form(None),
    ad_state: Optional[str] = Form(None),
    ad_discount: Optional[str] = Form(None),
    ad_price: Optional[str] = Form(None),
    ad_address: Optional[str] = Form(None),
    team_message: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    تعديل الإعلان مع إمكانية تحديث الصورة
    
    Form Data:
    - ad_ID: معرف الإعلان (مطلوب)
    - ad_image_url: رابط الصورة الجديدة (اختياري - استخدم هذا إذا رفعت الصورة إلى Firebase مسبقاً)
    - image: ملف الصورة (اختياري - سيتم تحويلها إلى base64)
    - clinic_name: اسم العيادة (اختياري)
    - وبقية الحقول...
    
    ملاحظة: يُفضل رفع الصورة إلى Firebase أولاً ثم إرسال ad_image_url
    
    يتطلب: Doctor-Secret header
    """
    if not ad_ID:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "bad_request", "message": "ad_ID مطلوب"}}
        )
    
    # البحث عن الإعلان
    ads = db.query(models.Ad).all()
    found_ad = None
    
    for ad in ads:
        try:
            data = json.loads(ad.payload_json) if ad.payload_json else {}
            if data.get("ad_ID") == ad_ID:
                found_ad = ad
                break
        except Exception:
            continue
    
    if not found_ad:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "الإعلان غير موجود"}}
        )
    
    # تحميل البيانات الحالية
    data = json.loads(found_ad.payload_json) if found_ad.payload_json else {}
    
    # تحديث رابط الصورة إذا تم إرساله
    if ad_image_url:
        data["ad_image_url"] = ad_image_url
        print(f"[UPDATE_AD] Image URL updated for ad {ad_ID}")
    
    # معالجة ملف الصورة إذا تم رفعه (كـ base64)
    elif image and image.filename:
        try:
            # قراءة محتوى الصورة
            image_content = await image.read()
            
            # تحويل إلى base64 (للاستخدام المؤقت)
            image_base64 = base64.b64encode(image_content).decode('utf-8')
            
            # حفظ كـ data URL
            # ⚠️ ملاحظة: يُفضل رفع الصورة إلى Firebase Storage للحصول على URL دائم
            data["ad_image_url"] = f"data:image/jpeg;base64,{image_base64}"
            
            print(f"[UPDATE_AD] Image file uploaded for ad {ad_ID}, size: {len(image_content)} bytes")
            
        except Exception as e:
            print(f"[UPDATE_AD] Error processing image: {e}")
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "image_error", "message": f"خطأ في معالجة الصورة: {str(e)}"}}
            )
    
    # تحديث الحقول الأخرى
    if clinic_name is not None:
        data["clinic_name"] = clinic_name
    if ad_subtitle is not None:
        data["ad_subtitle"] = ad_subtitle
    if ad_description is not None:
        data["ad_description"] = ad_description
    if ad_phonenumber is not None:
        data["ad_phonenumber"] = _to_ascii_digits(ad_phonenumber)
    if ad_state is not None:
        data["ad_state"] = ad_state
    if ad_discount is not None:
        data["ad_discount"] = _to_ascii_digits(ad_discount)
    if ad_price is not None:
        data["ad_price"] = _to_ascii_digits(ad_price)
    if ad_address is not None:
        data["ad_address"] = ad_address
    if team_message is not None:
        data["team_message"] = team_message
    
    # حفظ التغييرات
    found_ad.payload_json = json.dumps(data, ensure_ascii=False)
    db.add(found_ad)
    db.commit()
    db.refresh(found_ad)
    
    return {
        "message": "تم تحديث الإعلان بنجاح",
        "ad_ID": ad_ID,
        "updated_data": data
    }


@router.post("/update_ad")
def update_ad(
    payload: dict,
    db: Session = Depends(get_db),
    _: None = Depends(require_profile_secret)
):
    """
    تعديل بيانات الإعلان (الحقول المسموح بتعديلها فقط)
    
    Body:
    {
        "ad_ID": "85_abc123_1234567890",
        "created_date": "23/10/2025",
        "clinic_name": "عيادة الأسنان",
        "ad_image_url": "https://...",
        "ad_status": "active",
        "ad_phone": "٠١٠١٢٣٤٥٦٧٨",
        "ad_description": "عرض خاص",
        "ad_state": "القاهرة",
        "ad_price": "١٠٠",
        "discount_percentage": "٢٠",
        "clinic_address": "شارع ...",
        "ad_location": "https://..."
    }
    
    يتطلب: Doctor-Secret header
    """
    ad_id = payload.get("ad_ID")
    if not ad_id:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "bad_request", "message": "ad_ID is required"}}
        )
    
    # الحقول المسموح بتعديلها
    allowed_fields = [
        "created_date",
        "request_date",
        "clinic_name",
        "ad_subtitle",
        "ad_image_url",
        "ad_status",
        "ad_phone",
        "ad_phonenumber",
        "ad_description",
        "ad_address",
        "ad_state",
        "ad_price",
        "discount_percentage",
        "ad_discount",
        "clinic_address",
        "ad_location"
    ]
    
    # البحث عن الإعلان
    ads = db.query(models.Ad).all()
    
    for ad in ads:
        try:
            data = json.loads(ad.payload_json) if ad.payload_json else {}
            if data.get("ad_ID") == ad_id:
                # تحديث الحقول المسموح بها فقط
                for field in allowed_fields:
                    if field in payload:
                        # معالجة خاصة للأرقام
                        if field in ["ad_phone", "ad_phonenumber"]:
                            data["ad_phonenumber"] = _to_ascii_digits(payload[field])
                        elif field in ["ad_price"]:
                            data["ad_price"] = _to_ascii_digits(payload[field])
                        elif field in ["discount_percentage", "ad_discount"]:
                            data["ad_discount"] = _to_ascii_digits(payload[field])
                        elif field == "ad_status":
                            # تحويل ad_status إلى boolean
                            status_value = _parse_bool(payload[field])
                            data["ad_status"] = status_value
                            ad.ad_status = status_value
                        else:
                            data[field] = payload[field]
                
                # حفظ التغييرات
                ad.payload_json = json.dumps(data, ensure_ascii=False)
                db.add(ad)
                db.commit()
                db.refresh(ad)
                
                return {
                    "message": "تم تحديث الإعلان بنجاح",
                    "ad_ID": ad_id,
                    "updated_data": data
                }
        except Exception as e:
            continue
    
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "not_found", "message": "Ad not found"}}
    )


