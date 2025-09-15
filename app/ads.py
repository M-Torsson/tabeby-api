from __future__ import annotations
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .database import SessionLocal
from . import models

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
