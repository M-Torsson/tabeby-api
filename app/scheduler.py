# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from .database import SessionLocal
from . import models
from .timezone_utils import now_iraq
import json


scheduler = BackgroundScheduler()


def archive_old_bookings():
    """
    أرشفة جميع الحجوزات القديمة (قبل اليوم الحالي)
    - حفظ البيانات في booking_archives
    - حذف الأيام القديمة من booking_tables
    """
    
    db = SessionLocal()
    try:
        today_iraq = now_iraq().date()
        today_str = today_iraq.strftime("%Y-%m-%d")
        
        
        all_tables = db.query(models.BookingTable).all()
        
        archived_count = 0
        deleted_days_count = 0
        
        for bt in all_tables:
            clinic_id = bt.clinic_id
            
            try:
                days_data = json.loads(bt.days_json) if bt.days_json else {}
            except json.JSONDecodeError:
                continue
            
            if not isinstance(days_data, dict):
                continue
            
            old_days = {}
            new_days = {}
            
            for date_key, day_obj in days_data.items():
                try:
                    day_date = datetime.strptime(date_key, "%Y-%m-%d").date()
                    
                    if day_date < today_iraq:
                        old_days[date_key] = day_obj
                    else:
                        new_days[date_key] = day_obj
                        
                except ValueError:
                    new_days[date_key] = day_obj  # الاحتفاظ بالتواريخ غير الصالحة
            
            for date_key, day_obj in old_days.items():
                try:
                    existing_archive = db.query(models.BookingArchive).filter(
                        models.BookingArchive.clinic_id == clinic_id,
                        models.BookingArchive.table_date == date_key
                    ).first()
                    
                    if existing_archive:
                        continue
                    
                    patients = day_obj.get("patients", [])
                    capacity_total = day_obj.get("capacity_total", 0)
                    
                    capacity_served = sum(1 for p in patients if p.get("status") in ["تمت المعاينة", "served"])
                    capacity_cancelled = sum(1 for p in patients if p.get("status") in ["ملغى", "cancelled"])
                    
                    archive = models.BookingArchive(
                        clinic_id=clinic_id,
                        table_date=date_key,
                        capacity_total=capacity_total,
                        capacity_served=capacity_served,
                        capacity_cancelled=capacity_cancelled,
                        patients_json=json.dumps(patients, ensure_ascii=False)
                    )
                    
                    db.add(archive)
                    archived_count += 1
                    deleted_days_count += 1
                    
                    
                except Exception as e:
                    continue
            
            if old_days:
                bt.days_json = json.dumps(new_days, ensure_ascii=False)
                db.add(bt)
        
        db.commit()
        
        
    except Exception as e:
        db.rollback()
    finally:
        db.close()


def archive_old_golden_bookings():
    """
    أرشفة جميع الحجوزات الذهبية القديمة (قبل اليوم الحالي)
    - حفظ البيانات في golden_booking_archives
    - حذف الأيام القديمة من golden_booking_tables
    """
    
    db = SessionLocal()
    try:
        today_iraq = now_iraq().date()
        today_str = today_iraq.strftime("%Y-%m-%d")
        
        
        all_golden_tables = db.query(models.GoldenBookingTable).all()
        
        archived_count = 0
        deleted_days_count = 0
        
        for gt in all_golden_tables:
            clinic_id = gt.clinic_id
            
            try:
                days_data = json.loads(gt.days_json) if gt.days_json else {}
            except json.JSONDecodeError:
                continue
            
            if not isinstance(days_data, dict):
                continue
            
            old_days = {}
            new_days = {}
            
            for date_key, day_obj in days_data.items():
                try:
                    day_date = datetime.strptime(date_key, "%Y-%m-%d").date()
                    
                    if day_date < today_iraq:
                        old_days[date_key] = day_obj
                    else:
                        new_days[date_key] = day_obj
                        
                except ValueError:
                    new_days[date_key] = day_obj  # الاحتفاظ بالتواريخ غير الصالحة
            
            for date_key, day_obj in old_days.items():
                try:
                    existing_archive = db.query(models.GoldenBookingArchive).filter(
                        models.GoldenBookingArchive.clinic_id == clinic_id,
                        models.GoldenBookingArchive.table_date == date_key
                    ).first()
                    
                    if existing_archive:
                        continue
                    
                    patients = day_obj.get("patients", [])
                    capacity_total = day_obj.get("capacity_total", 0)
                    
                    capacity_served = sum(1 for p in patients if p.get("status") in ["تمت المعاينة", "served"])
                    capacity_cancelled = sum(1 for p in patients if p.get("status") in ["ملغى", "cancelled"])
                    
                    archive = models.GoldenBookingArchive(
                        clinic_id=clinic_id,
                        table_date=date_key,
                        capacity_total=capacity_total,
                        capacity_served=capacity_served,
                        capacity_cancelled=capacity_cancelled,
                        patients_json=json.dumps(patients, ensure_ascii=False)
                    )
                    
                    db.add(archive)
                    archived_count += 1
                    deleted_days_count += 1
                    
                    
                except Exception as e:
                    continue
            
            if old_days:
                gt.days_json = json.dumps(new_days, ensure_ascii=False)
                db.add(gt)
        
        db.commit()
        
        
    except Exception as e:
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    """
    تشغيل المجدول للأرشفة التلقائية
    يعمل يوميًا في الساعة 12:00 ليلاً بتوقيت العراق (UTC+3)
    """
    scheduler.add_job(
        archive_old_bookings,
        trigger=CronTrigger(hour=21, minute=0, timezone="UTC"),  # 21:00 UTC = 00:00 Iraq
        id="archive_old_bookings",
        name="أرشفة الحجوزات القديمة",
        replace_existing=True
    )
    
    scheduler.add_job(
        archive_old_golden_bookings,
        trigger=CronTrigger(hour=21, minute=5, timezone="UTC"),  # 21:05 UTC = 00:05 Iraq (بفارق 5 دقائق)
        id="archive_old_golden_bookings",
        name="أرشفة الحجوزات الذهبية القديمة",
        replace_existing=True
    )
    
    scheduler.start()


def shutdown_scheduler():
    """
    إيقاف المجدول عند إغلاق التطبيق
    """
    if scheduler.running:
        scheduler.shutdown()
