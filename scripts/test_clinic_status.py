"""
سكريبت اختبار سريع لـ APIs حالة العيادة (close_clinic)
"""
import sys
import os

# إضافة المجلد الجذر للمشروع
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient

# تعيين السر للاختبار قبل استيراد التطبيق
os.environ['DOCTOR_PROFILE_SECRET'] = os.environ.get('DOCTOR_PROFILE_SECRET', 'test-secret')

from app.main import app

client = TestClient(app)
headers = {'Doctor-Secret': os.environ['DOCTOR_PROFILE_SECRET']}

print("=" * 50)
print("اختبار APIs حالة العيادة")
print("=" * 50)

# 1. اختبار POST - إغلاق العيادة
print("\n1. إغلاق العيادة 85...")
response = client.post(
    '/api/close_clinic',
    json={'clinic_id': 85, 'is_closed': True},
    headers=headers
)
print(f"   الحالة: {response.status_code}")
print(f"   الاستجابة: {response.json()}")

# 2. اختبار GET - الحصول على حالة العيادة
print("\n2. الحصول على حالة العيادة 85...")
response = client.get(
    '/api/close_clinic?clinic_id=85',
    headers=headers
)
print(f"   الحالة: {response.status_code}")
print(f"   الاستجابة: {response.json()}")

# 3. اختبار POST - فتح العيادة
print("\n3. فتح العيادة 85...")
response = client.post(
    '/api/close_clinic',
    json={'clinic_id': 85, 'is_closed': False},
    headers=headers
)
print(f"   الحالة: {response.status_code}")
print(f"   الاستجابة: {response.json()}")

# 4. اختبار GET - التحقق من الفتح
print("\n4. التحقق من حالة العيادة 85...")
response = client.get(
    '/api/close_clinic?clinic_id=85',
    headers=headers
)
print(f"   الحالة: {response.status_code}")
print(f"   الاستجابة: {response.json()}")

# 5. اختبار عيادة جديدة (لم تُسجل من قبل)
print("\n5. الحصول على حالة عيادة جديدة 999...")
response = client.get(
    '/api/close_clinic?clinic_id=999',
    headers=headers
)
print(f"   الحالة: {response.status_code}")
print(f"   الاستجابة: {response.json()}")

# 6. اختبار بدون Secret Header
print("\n6. اختبار بدون Secret Header (يجب أن يفشل)...")
response = client.get('/api/close_clinic?clinic_id=85')
print(f"   الحالة: {response.status_code}")
print(f"   الاستجابة: {response.json()}")

print("\n" + "=" * 50)
print("اكتمل الاختبار!")
print("=" * 50)
