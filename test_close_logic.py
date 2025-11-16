# -*- coding: utf-8 -*-
"""
اختبار بسيط: فحص إذا كان close_table يحفظ حالة المرضى الصحيحة في الأرشيف
"""
from app.database import SessionLocal
from app.models import GoldenBookingTable, GoldenBookingArchive
import json

db = SessionLocal()

# ابحث عن يوم ذهبي موجود
gt = db.query(GoldenBookingTable).first()

if not gt:
    print("❌ لا يوجد جداول ذهبية في database")
    db.close()
    exit()

print(f"🔍 وجد جدول ذهبي: clinic_id={gt.clinic_id}")

try:
    days = json.loads(gt.days_json) if gt.days_json else {}
except:
    days = {}

if not days:
    print("❌ لا يوجد أيام في الجدول")
    db.close()
    exit()

# خذ أول يوم
first_date = list(days.keys())[0]
day_obj = days[first_date]

print(f"\n📅 يوم: {first_date}")
print(f"   حالة اليوم: {day_obj.get('status')}")

patients = day_obj.get("patients", [])
print(f"   عدد المرضى: {len(patients)}")

if not patients:
    print("❌ لا يوجد مرضى في هذا اليوم")
    db.close()
    exit()

print("\n👥 حالة المرضى الحالية:")
for i, p in enumerate(patients[:5], 1):
    if isinstance(p, dict):
        print(f"   {i}. {p.get('patientName', 'N/A')} - {p.get('status', 'N/A')}")

# الآن نحاكي كود close_table - نفس المنطق بالضبط
print("\n🔧 محاكاة كود close_table:")
print("   الخطوة 1: تغيير حالة المرضى إلى ملغى...")

# الكود القديم (WRONG):
old_patients_list = day_obj.get("patients", [])
for patient in old_patients_list:
    if isinstance(patient, dict):
        if patient.get("status") not in ("تمت المعاينة", "served"):
            patient["status"] = "ملغى"

day_obj["patients"] = old_patients_list
day_obj["status"] = "closed"
days[first_date] = day_obj

print("   الخطوة 2: قراءة patients للأرشيف...")

# الكود القديم (WRONG) - يقرأ من day_obj القديم
wrong_patients = day_obj.get("patients", [])

# الكود الجديد (CORRECT) - يقرأ من days المحدث
correct_patients = days[first_date].get("patients", [])

print("\n📊 مقارنة:")
print(f"   قراءة من day_obj القديم (WRONG): {len(wrong_patients)} مرضى")
print(f"   قراءة من days المحدث (CORRECT): {len(correct_patients)} مرضى")

print("\n   حالة المرضى بعد التعديل (CORRECT):")
cancelled_count = 0
served_count = 0
for i, p in enumerate(correct_patients[:5], 1):
    if isinstance(p, dict):
        status = p.get('status')
        print(f"   {i}. {p.get('patientName', 'N/A')} - {status}")
        if status in ("ملغى", "cancelled"):
            cancelled_count += 1
        elif status in ("تمت المعاينة", "served"):
            served_count += 1

print(f"\n✅ النتيجة:")
print(f"   معاينة: {served_count}")
print(f"   ملغى: {cancelled_count}")
print(f"   المجموع: {len(correct_patients)}")

db.close()
