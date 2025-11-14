"""
اختبار نظام الأرشفة التلقائية
"""
from app.scheduler import archive_old_bookings, archive_old_golden_bookings
from app.database import SessionLocal
from app import models
import json
from datetime import datetime, timedelta

def test_archive_system():
    """اختبار نظام الأرشفة"""
    
    print("=" * 60)
    print("اختبار نظام الأرشفة التلقائية")
    print("=" * 60)
    
    db = SessionLocal()
    
    try:
        # عرض البيانات قبل الأرشفة
        print("\n📊 قبل الأرشفة:")
        print("-" * 60)
        
        booking_tables_count = db.query(models.BookingTable).count()
        golden_tables_count = db.query(models.GoldenBookingTable).count()
        archive_count = db.query(models.BookingArchive).count()
        golden_archive_count = db.query(models.GoldenBookingArchive).count()
        
        print(f"جداول الحجوزات العادية: {booking_tables_count}")
        print(f"جداول الحجوزات الذهبية: {golden_tables_count}")
        print(f"الحجوزات المؤرشفة: {archive_count}")
        print(f"الحجوزات الذهبية المؤرشفة: {golden_archive_count}")
        
        # عرض عينة من الأيام القديمة
        print("\n📅 عينة من الأيام في جداول الحجوزات:")
        print("-" * 60)
        
        today = datetime.now().date()
        
        for bt in db.query(models.BookingTable).limit(3):
            try:
                days = json.loads(bt.days_json) if bt.days_json else {}
                old_days = []
                new_days = []
                
                for date_key in days.keys():
                    try:
                        day_date = datetime.strptime(date_key, "%Y-%m-%d").date()
                        if day_date < today:
                            old_days.append(date_key)
                        else:
                            new_days.append(date_key)
                    except:
                        pass
                
                print(f"\nعيادة {bt.clinic_id}:")
                print(f"  - أيام قديمة: {len(old_days)} {old_days[:3]}")
                print(f"  - أيام حالية/مستقبلية: {len(new_days)} {new_days[:3]}")
                
            except Exception as e:
                print(f"  - خطأ في قراءة البيانات: {str(e)}")
        
        # تنفيذ الأرشفة
        print("\n🔄 جاري تنفيذ الأرشفة...")
        print("-" * 60)
        
        archive_old_bookings()
        archive_old_golden_bookings()
        
        # عرض البيانات بعد الأرشفة
        print("\n✅ بعد الأرشفة:")
        print("-" * 60)
        
        db.expire_all()  # تحديث البيانات من قاعدة البيانات
        
        archive_count_after = db.query(models.BookingArchive).count()
        golden_archive_count_after = db.query(models.GoldenBookingArchive).count()
        
        print(f"الحجوزات المؤرشفة: {archive_count_after} (+{archive_count_after - archive_count})")
        print(f"الحجوزات الذهبية المؤرشفة: {golden_archive_count_after} (+{golden_archive_count_after - golden_archive_count})")
        
        # عرض عينة من المؤرشفات
        print("\n📋 عينة من الأرشيفات الجديدة:")
        print("-" * 60)
        
        recent_archives = db.query(models.BookingArchive).order_by(models.BookingArchive.id.desc()).limit(5)
        
        for arch in recent_archives:
            patients = json.loads(arch.patients_json) if arch.patients_json else []
            print(f"\nعيادة {arch.clinic_id} - {arch.table_date}:")
            print(f"  - السعة الكلية: {arch.capacity_total}")
            print(f"  - المخدومين: {arch.capacity_served}")
            print(f"  - الملغيين: {arch.capacity_cancelled}")
            print(f"  - عدد المرضى: {len(patients)}")
        
        print("\n" + "=" * 60)
        print("✅ اكتمل الاختبار بنجاح!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ خطأ في الاختبار: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        db.close()


if __name__ == "__main__":
    test_archive_system()
