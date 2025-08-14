from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, text, or_, desc, asc
from typing import List, Optional
from .database import get_db
from .models import Department, Staff
from .schemas import DepartmentCreate, DepartmentUpdate, DepartmentOut, DepartmentListResponse, DepartmentStats, StaffListResponse, StaffItem
from .auth import oauth2_scheme, decode_token
from datetime import datetime

router = APIRouter()

# Helper: Authentication
async def require_auth(token: str = Depends(oauth2_scheme)):
    try:
        payload = decode_token(token)
        if not payload or payload.get("type") not in ("admin", "staff"):
            raise HTTPException(status_code=401, detail="رمز وصول غير صالح")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="رمز وصول غير صالح")

# 1. GET /departments
@router.get("/departments", response_model=DepartmentListResponse)
def list_departments(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("id"),
    sort_order: Optional[str] = Query("desc"),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
):
    require_auth(token)
    query = db.query(Department)
    if search:
        query = query.filter(or_(Department.name.ilike(f"%{search}%"), Department.head_of_department.ilike(f"%{search}%")))
    if status:
        query = query.filter(Department.status == status)
    total = query.count()
    sort_column = getattr(Department, sort_by, Department.id)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
    items = query.offset((page-1)*limit).limit(limit).all()
    return DepartmentListResponse(items=items, total=total)

# 2. POST /departments
@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    require_auth(token)
    exists = db.query(Department).filter(func.lower(Department.name) == payload.name.lower()).first()
    if exists:
        raise HTTPException(status_code=400, detail="اسم القسم مستخدم مسبقاً")
    dep = Department(**payload.dict(), created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    db.add(dep)
    db.commit()
    db.refresh(dep)
    return dep

# 3. GET /departments/{id}
@router.get("/departments/{id}", response_model=DepartmentOut)
def get_department(id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    require_auth(token)
    dep = db.query(Department).filter_by(id=id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="القسم غير موجود")
    return dep

# 4. PATCH /departments/{id}
@router.patch("/departments/{id}", response_model=DepartmentOut)
def update_department(id: int, payload: DepartmentUpdate, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    require_auth(token)
    dep = db.query(Department).filter_by(id=id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="القسم غير موجود")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(dep, k, v)
    dep.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(dep)
    return dep

# 5. DELETE /departments/{id}
@router.delete("/departments/{id}")
def delete_department(id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    require_auth(token)
    dep = db.query(Department).filter_by(id=id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="القسم غير موجود")
    db.delete(dep)
    db.commit()
    return {"message": "تم حذف القسم"}

# 6. POST /departments/{id}/activate
@router.post("/departments/{id}/activate")
def activate_department(id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    require_auth(token)
    dep = db.query(Department).filter_by(id=id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="القسم غير موجود")
    dep.status = "active"
    dep.updated_at = datetime.utcnow()
    db.commit()
    return {"id": dep.id, "status": dep.status}

# 7. POST /departments/{id}/deactivate
@router.post("/departments/{id}/deactivate")
def deactivate_department(id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    require_auth(token)
    dep = db.query(Department).filter_by(id=id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="القسم غير موجود")
    dep.status = "inactive"
    dep.updated_at = datetime.utcnow()
    db.commit()
    return {"id": dep.id, "status": dep.status}

# 8. GET /departments/stats
@router.get("/departments/stats", response_model=DepartmentStats)
def departments_stats(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    require_auth(token)
    total_departments = db.query(func.count(Department.id)).scalar() or 0
    active_departments = db.query(func.count(Department.id)).filter(Department.status == "active").scalar() or 0
    inactive_departments = db.query(func.count(Department.id)).filter(Department.status == "inactive").scalar() or 0
    total_staff = db.query(func.count(Staff.id)).scalar() or 0
    total_services = db.query(func.sum(Department.services_count)).scalar() or 0
    growth_rate = 0.0  # يمكن حسابه حسب البيانات التاريخية
    return DepartmentStats(
        total_departments=total_departments,
        active_departments=active_departments,
        inactive_departments=inactive_departments,
        total_staff=total_staff,
        total_services=total_services,
        growth_rate=growth_rate,
    )

# 9. GET /staff (لصفحة إضافة قسم)
@router.get("/staff", response_model=StaffListResponse)
def list_staff(
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
):
    require_auth(token)
    query = db.query(Staff)
    if search:
        query = query.filter(or_(Staff.name.ilike(f"%{search}%"), Staff.email.ilike(f"%{search}%")))
    if status:
        query = query.filter(Staff.status == status)
    total = query.count()
    items = query.offset((page-1)*limit).limit(limit).all()
    return StaffListResponse(items=items, total=total)
