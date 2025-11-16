# -*- coding: utf-8 -*-
"""
اختبار على production server
"""
import requests
import json
import os

# استخدم secret حقيقي
secret = os.environ.get('DOCTOR_PROFILE_SECRET', 'test-secret')
headers = {'Doctor-Secret': secret}

base_url = 'https://tabeby-api.onrender.com'

print("=" * 80)
print("فحص production server")
print("=" * 80)

# 1. فحص health
print("\n1️⃣ فحص الصحة:")
r = requests.get(f'{base_url}/health')
if r.status_code == 200:
    data = r.json()
    print(f"   ✅ السيرفر شغال - Version: {data.get('version')}")
else:
    print(f"   ❌ خطأ: {r.status_code}")
    exit()

# 2. فحص جدول ذهبي
print("\n2️⃣ فحص الجداول الذهبية:")
r2 = requests.get(f'{base_url}/api/booking_golden_days?clinic_id=4', headers=headers)
if r2.status_code == 200:
    data = r2.json()
    days = data.get('days', {})
    print(f"   عدد الأيام: {len(days)}")
    print(f"   التواريخ: {list(days.keys())}")
    
    if '2025-11-17' in days:
        print("\n   ⚠️ يوم 2025-11-17 لا يزال موجوداً!")
        day = days['2025-11-17']
        print(f"   حالة اليوم: {day.get('status')}")
        print(f"   عدد المرضى: {len(day.get('patients', []))}")
    else:
        print("\n   ✅ يوم 2025-11-17 غير موجود (تم حذفه)")
else:
    print(f"   Status: {r2.status_code}")
    print(f"   Response: {r2.text[:200]}")

print("\n" + "=" * 80)
