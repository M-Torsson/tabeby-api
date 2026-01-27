# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional

from . import models, schemas
from .auth import get_current_admin, get_db

router = APIRouter(
    prefix="/departments",
    tags=["Departments"],
    dependencies=[Depends(get_current_admin)]
)

# 1. GET /departments - List departments
@router.get("", response_model=schemas.DepartmentListResponse)
def list_departments(
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    status: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    query = db.query(models.Department)

    if search:
        query = query.filter(
            or_(
                models.Department.name.ilike(f"%{search}%"),
                models.Department.head_of_department.ilike(f"%{search}%")
            )
        )

    if status:
        query = query.filter(models.Department.status == status)

    # Sorting
    if hasattr(models.Department, sort_by):
        if sort_order.lower() == "desc":
            query = query.order_by(getattr(models.Department, sort_by).desc())
        else:
            query = query.order_by(getattr(models.Department, sort_by).asc())

    total = query.count()
    items = query.offset((page - 1) * limit).limit(limit).all()
    
    # Manually calculate staff_count for each department
    for dept in items:
        dept.staff_count = db.query(models.Staff).filter(models.Staff.department == dept.name).count()


    return {"items": items, "total": total}

# 2. POST /departments - Create a new department
@router.post("", response_model=schemas.DepartmentOut, status_code=status.HTTP_201_CREATED)
def create_department(
    department: schemas.DepartmentCreate,
    db: Session = Depends(get_db)
):
    db_department = models.Department(**department.model_dump())
    db.add(db_department)
    db.commit()
    db.refresh(db_department)
    return db_department

# 3. GET /departments/{id} - Get a single department
@router.get("/{id}", response_model=schemas.DepartmentOut)
def get_department(id: int, db: Session = Depends(get_db)):
    db_department = db.query(models.Department).filter(models.Department.id == id).first()
    if db_department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    
    # Manually calculate staff_count
    db_department.staff_count = db.query(models.Staff).filter(models.Staff.department == db_department.name).count()
    
    return db_department

# 4. PATCH /departments/{id} - Update a department
@router.patch("/{id}", response_model=schemas.DepartmentOut)
def update_department(
    id: int,
    department: schemas.DepartmentUpdate,
    db: Session = Depends(get_db)
):
    db_department = db.query(models.Department).filter(models.Department.id == id).first()
    if db_department is None:
        raise HTTPException(status_code=404, detail="Department not found")

    update_data = department.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_department, key, value)

    db.add(db_department)
    db.commit()
    db.refresh(db_department)
    return db_department

# 5. DELETE /departments/{id} - Delete a department
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(id: int, db: Session = Depends(get_db)):
    db_department = db.query(models.Department).filter(models.Department.id == id).first()
    if db_department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    db.delete(db_department)
    db.commit()
    return None

# 6. POST /departments/{id}/activate - Activate a department
@router.post("/{id}/activate", response_model=schemas.DepartmentOut)
def activate_department(id: int, db: Session = Depends(get_db)):
    db_department = db.query(models.Department).filter(models.Department.id == id).first()
    if db_department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    db_department.status = "active"
    db.commit()
    db.refresh(db_department)
    return db_department

# 7. POST /departments/{id}/deactivate - Deactivate a department
@router.post("/{id}/deactivate", response_model=schemas.DepartmentOut)
def deactivate_department(id: int, db: Session = Depends(get_db)):
    db_department = db.query(models.Department).filter(models.Department.id == id).first()
    if db_department is None:
        raise HTTPException(status_code=404, detail="Department not found")
    db_department.status = "inactive"
    db.commit()
    db.refresh(db_department)
    return db_department

# 8. GET /departments/stats - Get department statistics
@router.get("/stats", response_model=schemas.DepartmentStats)
def get_department_stats(db: Session = Depends(get_db)):
    total_departments = db.query(models.Department).count()
    active_departments = db.query(models.Department).filter(models.Department.status == 'active').count()
    inactive_departments = total_departments - active_departments
    total_staff = db.query(models.Staff).count()
    
    # These are placeholders as per schema.
    # You might need to adjust the logic based on your actual data.
    total_services = db.query(func.sum(models.Department.services_count)).scalar() or 0
    
    # Placeholder for growth rate
    growth_rate = 12.5 

    return {
        "total_departments": total_departments,
        "active_departments": active_departments,
        "inactive_departments": inactive_departments,
        "total_staff": total_staff,
        "total_services": total_services,
        "growth_rate": growth_rate,
    }
