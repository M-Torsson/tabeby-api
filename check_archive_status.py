# -*- coding: utf-8 -*-
from app.database import SessionLocal
from app.models import GoldenBookingArchive, BookingArchive
import json

db = SessionLocal()

print("=" * 80)
print("فحص الأرشيف الذهبي (آخر 3 سجلات)")
print("=" * 80)

golden_archives = db.query(GoldenBookingArchive).order_by(GoldenBookingArchive.id.desc()).limit(3).all()

for i, arch in enumerate(golden_archives, 1):
    print(f"\n{i}. Clinic ID: {arch.clinic_id} | التاريخ: {arch.table_date}")
    print(f"   إجمالي: {arch.capacity_total} | معاينة: {arch.capacity_served} | ملغى: {arch.capacity_cancelled}")
    
    if arch.patients_json:
        try:
            patients = json.loads(arch.patients_json)
            print(f"   عدد المرضى في JSON: {len(patients)}")
            if patients:
                print("   أول 3 مرضى:")
                for j, p in enumerate(patients[:3], 1):
                    if isinstance(p, dict):
                        print(f"     {j}. {p.get('patientName')} - حالة: {p.get('status')}")
        except:
            print("   خطأ في قراءة patients_json")

print("\n" + "=" * 80)
print("فحص الأرشيف العادي (آخر 3 سجلات)")
print("=" * 80)

regular_archives = db.query(BookingArchive).order_by(BookingArchive.id.desc()).limit(3).all()

for i, arch in enumerate(regular_archives, 1):
    print(f"\n{i}. Clinic ID: {arch.clinic_id} | التاريخ: {arch.table_date}")
    print(f"   إجمالي: {arch.capacity_total} | معاينة: {arch.capacity_served} | ملغى: {arch.capacity_cancelled}")
    
    if arch.patients_json:
        try:
            patients = json.loads(arch.patients_json)
            print(f"   عدد المرضى في JSON: {len(patients)}")
            if patients:
                print("   أول 3 مرضى:")
                for j, p in enumerate(patients[:3], 1):
                    if isinstance(p, dict):
                        print(f"     {j}. {p.get('patientName')} - حالة: {p.get('status')}")
        except:
            print("   خطأ في قراءة patients_json")

db.close()
