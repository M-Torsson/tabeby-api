from __future__ import annotations
import json
import re
import os
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import SessionLocal
from . import models
from .auth import get_current_admin  # kept for potential reuse, but not required for public endpoints

router = APIRouter(prefix="/api", tags=["Doctors"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def error(code: str, message: str, status: int = 400):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def require_profile_secret(request: Request):
    """Require a static secret for accessing doctor profile.
    - Set DOCTOR_PROFILE_SECRET in environment.
    - Client must send Doctor-Secret header with the exact same value.
    If header is missing or does not match, return 403.
    """
    secret = os.getenv("DOCTOR_PROFILE_SECRET") or ""
    provided = request.headers.get("Doctor-Secret")
    if not provided or provided != secret:
        raise HTTPException(status_code=403, detail="forbidden")


def _to_ascii_digits(s: str | None) -> Optional[str]:
    if s is None:
        return None
    trans = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    return s.translate(trans)


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    try:
        return int(_to_ascii_digits(str(v)).strip())
    except Exception:
        return None


def _safe_bool(v: Any, default: Optional[bool] = None) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return default


DEFAULT_PROFILE = {
    "general_info": {
        "doctor_name": "Doctor",
        "email_address": "doctor@example.com",
        "doctor_phone_number": "",
        "experience_years": "0",
        "clinic_states": "",
        "accountStatus": True,
    },
    "specializations": ["General"],
    "clinic_phone_number": {"phone_1": "", "phone_2": "", "phone_3": ""},
    "clinic_location": {"latitude": "", "longitude": "", "place_name": ""},
}


def _extract_clinic_id_from_profile_json(profile_json: str | None) -> Optional[int]:
    if not profile_json:
        return None
    try:
        obj = json.loads(profile_json)
        if isinstance(obj, dict):
            g = obj.get("general_info", {})
            if isinstance(g, dict):
                return _safe_int(g.get("clinic_id"))
    except Exception:
        return None
    return None

def _extract_clinic_name_from_profile_json(profile_json: str | None) -> Optional[str]:
    if not profile_json:
        return None
    try:
        obj = json.loads(profile_json)
        if isinstance(obj, dict):
            g = obj.get("general_info", {})
            if isinstance(g, dict):
                name = g.get("clinic_name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
    except Exception:
        return None
    return None

def _extract_location_from_profile_json(profile_json: str | None) -> Dict[str, Optional[str]]:
    lat = lon = place = None
    if profile_json:
        try:
            obj = json.loads(profile_json)
            if isinstance(obj, dict):
                loc = obj.get("clinic_location")
                if isinstance(loc, dict):
                    lat = (loc.get("latitude") if isinstance(loc.get("latitude"), str) else str(loc.get("latitude"))) if loc.get("latitude") is not None else None
                    lon = (loc.get("longitude") if isinstance(loc.get("longitude"), str) else str(loc.get("longitude"))) if loc.get("longitude") is not None else None
                    place = loc.get("place_name") if isinstance(loc.get("place_name"), str) else None
        except Exception:
            pass
    return {"latitude": lat, "longitude": lon, "place_name": place}


def _denormalize_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    g = profile.get("general_info", {}) if isinstance(profile.get("general_info"), dict) else {}
    name = g.get("doctor_name") or "Doctor"
    email = g.get("email_address") or None
    phone = g.get("doctor_phone_number") or None
    experience = _safe_int(g.get("experience_years"))
    patients = _safe_int(g.get("number_patients_treated"))
    # دعم المفتاح الجديد account_status بالإضافة إلى accountStatus القديم
    status_bool = _safe_bool(g.get("account_status"), default=None)
    if status_bool is None:
        status_bool = _safe_bool(g.get("accountStatus"), default=True)
    status = "active" if bool(status_bool) else "inactive"
    specialty = None
    specs = profile.get("specializations")
    if isinstance(specs, list) and specs:
        first = specs[0]
        if isinstance(first, dict):
            # يدعم الشكل الجديد [{id,name}]
            specialty = str(first.get("name") or "").strip() or None
        else:
            specialty = str(first)
    clinic_state = g.get("clinic_states") or None
    return {
        "name": name,
        "email": email,
        "phone": phone,
        "experience_years": experience,
        "patients_count": patients,
        "status": status,
        "specialty": specialty,
        "clinic_state": clinic_state,
    }


def _ensure_seed(db: Session) -> None:
    if db.query(models.Doctor).count() == 0:
        prof = DEFAULT_PROFILE
        den = _denormalize_profile(prof)
        row = models.Doctor(
            name=den["name"],
            email=den["email"],
            phone=den["phone"],
            experience_years=den["experience_years"],
            patients_count=den["patients_count"],
            status=den["status"],
            specialty=den["specialty"],
            clinic_state=den["clinic_state"],
            profile_json=json.dumps(prof, ensure_ascii=False),
        )
        db.add(row)
        db.commit()


@router.get("/doctors")
def list_doctors(
    q: Optional[str] = None,
    specialty: Optional[str] = None,
    status: Optional[str] = None,
    expMin: Optional[int] = None,
    expMax: Optional[int] = None,
    page: int = 1,
    pageSize: int = 20,
    sort: Optional[str] = None,
    db: Session = Depends(get_db),
):
    _ensure_seed(db)
    page = max(1, page)
    pageSize = max(1, min(pageSize, 100))

    query = db.query(models.Doctor)
    if q:
        ql = f"%{q.lower()}%"
        query = query.filter(
            func.lower(models.Doctor.name).like(ql)
            | func.lower(models.Doctor.email).like(ql)
            | func.lower(models.Doctor.phone).like(ql)
        )
    if specialty:
        query = query.filter(models.Doctor.specialty == specialty)
    if status:
        query = query.filter(models.Doctor.status == status)
    if expMin is not None:
        query = query.filter(models.Doctor.experience_years >= expMin)
    if expMax is not None:
        query = query.filter(models.Doctor.experience_years <= expMax)

    total = query.count()

    if sort:
        desc = sort.startswith("-")
        field = sort[1:] if desc else sort
        order_col = {
            "name": models.Doctor.name,
            "experience": models.Doctor.experience_years,
            "patients": models.Doctor.patients_count,
            "status": models.Doctor.status,
        }.get(field, models.Doctor.name)
        query = query.order_by(order_col.desc() if desc else order_col.asc())
    else:
        query = query.order_by(models.Doctor.name.asc())

    rows = query.offset((page - 1) * pageSize).limit(pageSize).all()
    items = [
        {
            "id": r.id,
            "name": r.name,
            "image": r.image_url,
            "specialty": r.specialty,
            "status": r.status,
            "patients": r.patients_count,
            "experience": r.experience_years,
            "email": r.email,
            "phone": r.phone,
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "pageSize": pageSize}


@router.get("/doctors/{doctor_id}")
def get_doctor(doctor_id: int, secret_ok: None = Depends(require_profile_secret), db: Session = Depends(get_db)):
    r = db.query(models.Doctor).filter_by(id=doctor_id).first()
    if not r:
        # سلوك صارم: هذا المسار يبحث فقط بالمعرّف الأساسي لسجل doctors
        return error("not_found", "Doctor not found", 404)
    try:
        profile = json.loads(r.profile_json) if r.profile_json else DEFAULT_PROFILE
    except Exception:
        profile = DEFAULT_PROFILE
    # account block
    acc = {
        "email": r.email,
        "phone": r.phone,
        "status": r.status,
    }
    # أعِد كل الحقول كما هي بالإضافة إلى account
    profile_out: Dict[str, Any] = {}
    if isinstance(profile, dict):
        profile_out = dict(profile)
    profile_out["account"] = acc
    return {"id": r.id, "profile": profile_out}


@router.get("/doctors/by-clinic-id/{clinic_id}")
@router.get("/doctors/clinic/{clinic_id}")
def get_doctor_by_clinic_id(clinic_id: int, secret_ok: None = Depends(require_profile_secret), db: Session = Depends(get_db)):
    rows = db.query(models.Doctor).filter(models.Doctor.profile_json.isnot(None)).all()
    matches = []
    for r in rows:
        cid = _extract_clinic_id_from_profile_json(r.profile_json)
        if cid is not None and cid == clinic_id:
            matches.append(r)

    if len(matches) == 0:
        return error("clinic_id_not_found", "clinic_id not found. Please verify the value.", 404)
    if len(matches) > 1:
        return error("clinic_id_duplicate", "clinic_id is duplicated in the database.", 409)

    r = matches[0]
    try:
        profile = json.loads(r.profile_json) if r.profile_json else DEFAULT_PROFILE
    except Exception:
        profile = DEFAULT_PROFILE
    acc = {"email": r.email, "phone": r.phone, "status": r.status}
    out = dict(profile) if isinstance(profile, dict) else {}
    out["account"] = acc
    return {"id": r.id, "profile": out}


@router.get("/doctor_profile")
def get_doctor_profile_api(doctor_id: int, secret_ok: None = Depends(require_profile_secret), db: Session = Depends(get_db)):
    """
    Endpoint مختصر لجلب بروفايل دكتور عن طريق ?doctor_id=123
    - محمي بهيدر Doctor-Secret المطابق لقيمة DOCTOR_PROFILE_SECRET
    - يُعيد نفس شكل الاستجابة مثل GET /api/doctors/{id}
    """
    r = db.query(models.Doctor).filter_by(id=doctor_id).first()
    if not r:
        return error("not_found", "Doctor not found", 404)
    try:
        profile = json.loads(r.profile_json) if r.profile_json else DEFAULT_PROFILE
    except Exception:
        profile = DEFAULT_PROFILE
    acc = {"email": r.email, "phone": r.phone, "status": r.status}
    profile_out: Dict[str, Any] = {}
    if isinstance(profile, dict):
        profile_out = dict(profile)
    profile_out["account"] = acc
    return {"id": r.id, "profile": profile_out}


@router.patch("/doctors/{doctor_id}")
async def update_doctor(doctor_id: int, request: Request, db: Session = Depends(get_db)):
    r = db.query(models.Doctor).filter_by(id=doctor_id).first()
    if not r:
        return error("not_found", "Doctor not found", 404)
    try:
        patch = await request.json()
        if not isinstance(patch, dict):
            raise ValueError("Invalid body")
    except Exception:
        return error("bad_request", "Invalid JSON body", 400)

    try:
        profile = json.loads(r.profile_json) if r.profile_json else {}
    except Exception:
        profile = {}
    # دمج مرن: دعم كل المفاتيح العليا، مع معالجة خاصة لحقل account لتحديث الأعمدة المنزوعة التطبيع
    for k, v in patch.items():
        if k == "account" and isinstance(v, dict):
            if "email" in v:
                r.email = v["email"] or None
            if "phone" in v:
                r.phone = v["phone"] or None
            if "status" in v:
                r.status = v["status"] or r.status
            continue
        # دمج dicts بشكل سطحي، وضع باقي الأنواع كما هي
        if isinstance(v, dict):
            base = profile.get(k) if isinstance(profile.get(k), dict) else {}
            base.update(v)
            profile[k] = base
        else:
            profile[k] = v
    # also update denormalized columns from general_info/specializations
    den = _denormalize_profile({**profile})
    if den.get("name"):
        r.name = den["name"]
    if den.get("experience_years") is not None:
        r.experience_years = den["experience_years"]
    if den.get("patients_count") is not None:
        r.patients_count = den["patients_count"]
    if den.get("specialty"):
        r.specialty = den["specialty"]
    if den.get("clinic_state"):
        r.clinic_state = den["clinic_state"]

    r.profile_json = json.dumps(profile, ensure_ascii=False)
    db.commit()
    return {"ok": True, "id": doctor_id}


@router.patch("/doctors/{doctor_id}/status")
def update_doctor_status(doctor_id: int, body: Dict[str, Any], db: Session = Depends(get_db)):
    r = db.query(models.Doctor).filter_by(id=doctor_id).first()
    if not r:
        return error("not_found", "Doctor not found", 404)
    active = body.get("active")
    if not isinstance(active, bool):
        return error("bad_request", "active must be boolean", 400)
    r.status = "active" if active else "inactive"
    db.commit()
    return {"id": r.id, "status": "Active" if r.status == "active" else "Inactive"}


@router.delete("/doctors/{doctor_id}")
def delete_doctor(doctor_id: int, db: Session = Depends(get_db)):
    r = db.query(models.Doctor).filter_by(id=doctor_id).first()
    if not r:
        return error("not_found", "Doctor not found", 404)
    db.delete(r)
    db.commit()
    return {"message": "deleted", "id": doctor_id}


@router.get("/lookups/specialties")
def lookup_specialties(db: Session = Depends(get_db)):
    rows = db.query(models.Doctor.specialty).filter(models.Doctor.specialty.isnot(None)).distinct().order_by(models.Doctor.specialty.asc()).all()
    return {"items": [r[0] for r in rows if r[0]]}


@router.get("/lookups/clinic-states")
def lookup_clinic_states(db: Session = Depends(get_db)):
    rows = db.query(models.Doctor.clinic_state).filter(models.Doctor.clinic_state.isnot(None)).distinct().order_by(models.Doctor.clinic_state.asc()).all()
    return {"items": [r[0] for r in rows if r[0]]}


@router.post("/doctors")
async def create_doctor(request: Request, db: Session = Depends(get_db)):
    """
    إنشاء طبيب جديد بدون مصادقة.
    Body يمكن أن يكون:
    - { profile: { general_info, clinic_location, clinic_phone_number, account } }
    - أو مباشرة { general_info, clinic_location, clinic_phone_number, account }
    """
    try:
        body = await request.json()
        if not isinstance(body, dict):
            raise ValueError
    except Exception:
        return error("bad_request", "Invalid JSON body", 400)

    profile = body.get("profile") if isinstance(body.get("profile"), dict) else {
        k: v for k, v in body.items() if k in {"general_info", "clinic_location", "clinic_phone_number", "account", "specializations"}
    }
    if not profile:
        profile = DEFAULT_PROFILE

    den = _denormalize_profile(profile)
    row = models.Doctor(
        name=den.get("name") or "Doctor",
        email=den.get("email"),
        phone=den.get("phone"),
        experience_years=den.get("experience_years"),
        patients_count=den.get("patients_count"),
        status=den.get("status") or "active",
        specialty=den.get("specialty"),
        clinic_state=den.get("clinic_state"),
        profile_json=json.dumps(profile, ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.get("/clinics")
def list_clinics(secret_ok: None = Depends(require_profile_secret), db: Session = Depends(get_db)):
    """
    يُرجع جميع العيادات بدون ترقيم صفحات:
    [ { clinic_id, doctor_name, profile_image_URL?, specializations } ]
    يتطلب Doctor-Secret.
    ملاحظة:
    - لا تُعاد أي مفاتيح إضافية (لا dents_addition ولا plastic_addition).
    - إذا احتوت specializations على تخصص رئيسي واحد ("طب اسنان" أو "طب أسنان" أو "جراحة تجميلية")
      بالإضافة إلى عناصر فرعية أخرى، فسيتم إبقاء التخصص الرئيسي فقط داخل specializations وإسقاط بقية العناصر.
    """
    rows = db.query(models.Doctor).filter(models.Doctor.profile_json.isnot(None)).order_by(models.Doctor.id.asc()).all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        try:
            obj = json.loads(r.profile_json) if r.profile_json else {}
        except Exception:
            obj = {}
        g = obj.get("general_info", {}) if isinstance(obj, dict) else {}
        cid = _safe_int(g.get("clinic_id")) if isinstance(g, dict) else None
        if cid is None:
            continue
        dname = g.get("doctor_name") if isinstance(g, dict) else None
        if not dname:
            dname = r.name
        # try obtain image url from denormalized column or profile JSON
        img_url: Optional[str] = r.image_url or None
        if not img_url and isinstance(obj, dict):
            def _pick_url(d: Dict[str, Any]) -> Optional[str]:
                for k in ("profile_image_URL", "profileImageUrl", "image_url", "imageUrl"):
                    v = d.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()
                return None
            img_url = _pick_url(obj)
            if not img_url:
                gg = obj.get("general_info")
                if isinstance(gg, dict):
                    img_url = _pick_url(gg)
        # specializations with ids if available
        specs_raw = obj.get("specializations") if isinstance(obj, dict) else None
        specs_full: List[Dict[str, Any]] = []
        if isinstance(specs_raw, list):
            for s in specs_raw:
                if isinstance(s, dict):
                    nm = s.get("name")
                    if isinstance(nm, str) and nm.strip():
                        sid = _safe_int(s.get("id"))
                        specs_full.append({"id": sid, "name": nm.strip()})
                else:
                    nm = str(s)
                    specs_full.append({"id": None, "name": nm})

        # (no additions returned in this endpoint)

        # derive additions from specializations if a main category is present
        def _norm_name(x: str) -> str:
            return (x or "").strip()

        dentistry_mains = {"طب اسنان", "طب أسنان"}
        plastic_mains = {"جراحة تجميلية"}

        has_dentistry_main = any(_norm_name(s.get("name")) in dentistry_mains for s in specs_full)
        has_plastic_main = any(_norm_name(s.get("name")) in plastic_mains for s in specs_full)

        if specs_full:
            mains: List[Dict[str, Any]] = []
            for s in specs_full:
                n = _norm_name(s.get("name"))
                if n in dentistry_mains or n in plastic_mains:
                    mains.append(s)

            # Only transform when exactly one main category is present to avoid ambiguity
            if has_dentistry_main and not has_plastic_main:
                specs_full = [s for s in mains if _norm_name(s.get("name")) in dentistry_mains]
            elif has_plastic_main and not has_dentistry_main:
                specs_full = [s for s in mains if _norm_name(s.get("name")) in plastic_mains]
            # else: keep specs_full as-is

        # Build item in required key order
        item: Dict[str, Any] = {
            "clinic_id": cid,
            "doctor_name": dname,
                # Force status to active in clinics listing per request
                "status": "active",
        }
        if img_url:
            item["profile_image_URL"] = img_url
        item["specializations"] = specs_full
        out.append(item)
    return out



