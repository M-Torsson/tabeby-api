"""
اختبار: نفس الـ endpoint مع دعم iOS و Android
"""
from fastapi.testclient import TestClient
from app.main import app
import os

os.environ['DOCTOR_PROFILE_SECRET'] = 'test-secret'

client = TestClient(app)
headers_base = {'Doctor-Secret': 'test-secret'}

print("=" * 80)
print("🧪 اختبار /api/clinics مع دعم iOS و Android")
print("=" * 80)

# الاختبار 1: طلب من Android (بدون header أو header مختلف)
print("\n1️⃣ طلب من Android (X-Platform: android أو بدون header)")
headers_android = {**headers_base, 'X-Platform': 'android'}
r1 = client.get('/api/clinics', headers=headers_android)
print(f"   STATUS: {r1.status_code}")

if r1.status_code == 200:
    clinics_android = r1.json()
    print(f"   عدد العيادات: {len(clinics_android)}")
    if clinics_android:
        first_clinic = clinics_android[0]
        print(f"   أول عيادة:")
        print(f"      - clinic_id: {first_clinic.get('clinic_id')}")
        print(f"      - doctor_name: {first_clinic.get('doctor_name')}")
        specs = first_clinic.get('specializations', [])
        if specs:
            print(f"      - specializations ({len(specs)}):")
            for s in specs[:3]:  # أول 3
                print(f"         • ID: {s.get('id')} - {s.get('name')}")

# الاختبار 2: طلب من iOS
print("\n2️⃣ طلب من iOS (X-Platform: iOS)")
headers_ios = {**headers_base, 'X-Platform': 'iOS'}
r2 = client.get('/api/clinics', headers=headers_ios)
print(f"   STATUS: {r2.status_code}")

if r2.status_code == 200:
    clinics_ios = r2.json()
    print(f"   عدد العيادات: {len(clinics_ios)}")
    if clinics_ios:
        first_clinic = clinics_ios[0]
        print(f"   أول عيادة:")
        print(f"      - clinic_id: {first_clinic.get('clinic_id')}")
        print(f"      - doctor_name: {first_clinic.get('doctor_name')}")
        specs = first_clinic.get('specializations', [])
        if specs:
            print(f"      - specializations ({len(specs)}):")
            for s in specs[:3]:  # أول 3
                spec_id = s.get('id')
                spec_name = s.get('name')
                print(f"         • ID: {spec_id} - {spec_name}")

# الاختبار 3: مقارنة IDs
print("\n3️⃣ مقارنة IDs بين Android و iOS:")

if r1.status_code == 200 and r2.status_code == 200:
    clinics_android = r1.json()
    clinics_ios = r2.json()
    
    # ابحث عن عيادة بها "طب الأسنان"
    for clinic_android in clinics_android:
        specs_android = clinic_android.get('specializations', [])
        for spec in specs_android:
            if 'أسنان' in spec.get('name', ''):
                # ابحث عن نفس العيادة في iOS
                clinic_id = clinic_android.get('clinic_id')
                clinic_ios = next((c for c in clinics_ios if c.get('clinic_id') == clinic_id), None)
                
                if clinic_ios:
                    specs_ios = clinic_ios.get('specializations', [])
                    spec_ios = next((s for s in specs_ios if 'أسنان' in s.get('name', '')), None)
                    
                    if spec_ios:
                        android_id = spec.get('id')
                        ios_id = spec_ios.get('id')
                        print(f"   العيادة #{clinic_id} - طب الأسنان:")
                        print(f"      Android ID: {android_id}")
                        print(f"      iOS ID: {ios_id}")
                        
                        if ios_id == 15:
                            print(f"      ✅ iOS ID صحيح (15 = طب الأسنان)")
                        else:
                            print(f"      ❌ iOS ID خطأ (يجب أن يكون 15)")
                break
        else:
            continue
        break

# الاختبار 4: التحقق من تخصصات أخرى
print("\n4️⃣ التحقق من تخصصات iOS الأخرى:")
if r2.status_code == 200:
    all_specs_ios = []
    for clinic in clinics_ios:
        all_specs_ios.extend(clinic.get('specializations', []))
    
    # إزالة التكرار بناءً على الاسم
    unique_specs = {}
    for spec in all_specs_ios:
        name = spec.get('name')
        if name and name not in unique_specs:
            unique_specs[name] = spec.get('id')
    
    # عرض بعض التخصصات
    print(f"   التخصصات الفريدة ({len(unique_specs)}):")
    for name, spec_id in list(unique_specs.items())[:10]:
        print(f"      • {name}: ID = {spec_id}")

print("\n" + "=" * 80)
print("✅ انتهى الاختبار")
print("=" * 80)
