# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .auth import get_current_admin, get_db
from . import models, schemas

router = APIRouter(tags=["Activity"])


def _parse_csv_list(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [v.strip() for v in value.split(",") if v.strip()]


@router.get("/users/me/activity", response_model=schemas.ActivityListResponse)
def list_my_activity(
    db: Session = Depends(get_db),
    current_admin: models.Admin = Depends(get_current_admin),
    page: Optional[int] = Query(default=1, ge=1),
    page_size: Optional[int] = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = None,
    since: Optional[datetime] = None,
    types: Optional[str] = None,
    status: Optional[str] = None,
    order: Optional[str] = Query(default="desc", pattern="^(asc|desc)$"),
):
    q = db.query(models.Activity).filter(models.Activity.admin_id == current_admin.id)

    if since:
        q = q.filter(models.Activity.at >= since)

    types_list = _parse_csv_list(types)
    status_list = _parse_csv_list(status)
    if types_list:
        q = q.filter(models.Activity.type.in_(types_list))
    if status_list:
        q = q.filter(models.Activity.status.in_(status_list))

    if order == "asc":
        q = q.order_by(models.Activity.at.asc())
    else:
        q = q.order_by(models.Activity.at.desc())

    total = q.count()

    if cursor:
        pass

    items = q.offset((page - 1) * page_size).limit(page_size).all()

    out_items = [
        schemas.ActivityOut.model_validate(it, from_attributes=True) for it in items if it.type != "backup_completed"
    ]

    return schemas.ActivityListResponse(items=out_items, total=total, nextCursor=None)


@router.post("/activity", response_model=schemas.ActivityOut, status_code=201)
def create_activity(payload: schemas.ActivityCreate, db: Session = Depends(get_db), current_admin: models.Admin = Depends(get_current_admin)):
    target_admin = current_admin
    if payload.email and payload.email != current_admin.email:
        raise HTTPException(status_code=403, detail="لا يمكن إنشاء حدث لمستخدم آخر")

    now = datetime.utcnow()
    at = payload.at or now

    activity = models.Activity(
        id=uuid.uuid4().hex,
        admin_id=target_admin.id,
        type=payload.type,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        at=at,
    )

    db.add(activity)
    db.commit()
    db.refresh(activity)

    return schemas.ActivityOut.model_validate(activity, from_attributes=True)
