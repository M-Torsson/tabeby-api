"""
اختبار مباشر: التحقق من تغيير حالة المرضى في قاعدة البيانات
"""
from app.main import get_db
from app import models
import json

db = next(get_db())

print("=" * 80)
print("🔍 التحقق من الأرشيف في قاعدة البيانات")
print("=" * 80)

# البحث عن أرشيف اليوم 2025-12-05
archive = db.query(models.GoldenBookingArchive).filter(
    models.GoldenBookingArchive.clinic_id == 85,
    models.GoldenBookingArchive.table_date == "2025-12-05"
).first()

if archive:
    print(f"\n✅ تم العثور على الأرشيف:")
    print(f"   التاريخ: {archive.table_date}")
    print(f"   السعة الكلية: {archive.capacity_total}")
    print(f"   المعاينين: {archive.capacity_served}")
    print(f"   الملغيين: {archive.capacity_cancelled}")
    
    patients = json.loads(archive.patients_json)
    print(f"\n📋 المرضى ({len(patients)} مريض):")
    
    for i, p in enumerate(patients, 1):
        name = p.get('name', 'N/A')
        status = p.get('status', 'N/A')
        emoji = "✅" if status in ("ملغى", "تمت المعاينة") else "⚠️"
        print(f"   {emoji} {i}. {name}: {status}")
    
    # التحقق من النتائج
    print(f"\n📊 التحقق:")
    
    # عد الملغيين
    cancelled_count = sum(1 for p in patients if p.get('status') == 'ملغى')
    served_count = sum(1 for p in patients if p.get('status') == 'تمت المعاينة')
    
    print(f"   - الملغيين: {cancelled_count}")
    print(f"   - المعاينين: {served_count}")
    print(f"   - capacity_cancelled في الجدول: {archive.capacity_cancelled}")
    
    if cancelled_count == archive.capacity_cancelled:
        print(f"   ✅ عدد الملغيين صحيح!")
    else:
        print(f"   ❌ عدم تطابق: {cancelled_count} != {archive.capacity_cancelled}")
else:
    print("\n❌ لم يتم العثور على الأرشيف")
    
    # البحث عن كل الأرشيفات
    all_archives = db.query(models.GoldenBookingArchive).filter(
        models.GoldenBookingArchive.clinic_id == 85
    ).all()
    
    print(f"\n📚 كل الأرشيفات المتوفرة ({len(all_archives)}):")
    for arch in all_archives:
        print(f"   - {arch.table_date}")

print("\n" + "=" * 80)
