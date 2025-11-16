# -*- coding: utf-8 -*-
from fastapi.testclient import TestClient
from app.main import app
import os

# Set secret for authentication
os.environ['DOCTOR_PROFILE_SECRET'] = os.environ.get('DOCTOR_PROFILE_SECRET', 'test-secret')

client = TestClient(app)
headers = {'Doctor-Secret': os.environ['DOCTOR_PROFILE_SECRET']}

print("📋 اختبار الحجوزات الذهبية:")
print("=" * 60)

# Get golden bookings for clinic 85
r = client.get('/golden_bookings/days/85', headers=headers)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    days = data.get('days', {})
    print(f"عدد الأيام: {len(days)}")
    print(f"أيام متاحة: {list(days.keys())}")
    
    if days:
        first_date = list(days.keys())[0]
        day_data = days[first_date]
        patients = day_data.get('patients', [])
        print(f"\nيوم {first_date}:")
        print(f"  حالة اليوم: {day_data.get('status')}")
        print(f"  عدد المرضى: {len(patients)}")
        if patients:
            print("  المرضى:")
            for i, p in enumerate(patients[:5], 1):
                if isinstance(p, dict):
                    print(f"    {i}. {p.get('patientName')} - حالة: {p.get('status')}")
