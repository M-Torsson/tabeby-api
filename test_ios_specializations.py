"""
اختبار iOS Specializations endpoint
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("=" * 80)
print("🧪 اختبار iOS Specializations API")
print("=" * 80)

# الاختبار 1: الحصول على جميع الاختصاصات
print("\n1️⃣ GET /ios/specializations - جميع الاختصاصات")
r1 = client.get('/ios/specializations')
print(f"   STATUS: {r1.status_code}")

if r1.status_code == 200:
    specs = r1.json()
    print(f"   عدد الاختصاصات: {len(specs)}")
    print(f"\n   أول 5 اختصاصات:")
    for spec in specs[:5]:
        print(f"      ID {spec['id']:2d}: {spec['name']}")
    
    print(f"\n   آخر 5 اختصاصات:")
    for spec in specs[-5:]:
        print(f"      ID {spec['id']:2d}: {spec['name']}")

# الاختبار 2: الحصول على تخصص واحد
print("\n2️⃣ GET /ios/specializations/1 - طبيب عام")
r2 = client.get('/ios/specializations/1')
print(f"   STATUS: {r2.status_code}")
if r2.status_code == 200:
    spec = r2.json()
    print(f"   {spec}")

print("\n3️⃣ GET /ios/specializations/15 - طب الأسنان")
r3 = client.get('/ios/specializations/15')
print(f"   STATUS: {r3.status_code}")
if r3.status_code == 200:
    spec = r3.json()
    print(f"   {spec}")

print("\n4️⃣ GET /ios/specializations/16 - جراحة تجميلة")
r4 = client.get('/ios/specializations/16')
print(f"   STATUS: {r4.status_code}")
if r4.status_code == 200:
    spec = r4.json()
    print(f"   {spec}")

# الاختبار 3: تخصص غير موجود
print("\n5️⃣ GET /ios/specializations/999 - غير موجود")
r5 = client.get('/ios/specializations/999')
print(f"   STATUS: {r5.status_code}")
if r5.status_code == 404:
    print(f"   ✅ رسالة الخطأ: {r5.json()['detail']}")

# الاختبار 4: التحقق من تطابق IDs مع Swift
print("\n6️⃣ التحقق من تطابق IDs مع Swift...")
swift_mapping = {
    1: "طبيب عام",
    2: "الجهاز الهضمي",
    3: "الصدرية والقلبية",
    8: "نسائية و توليد / رعاية حوامل",
    15: "طب الأسنان",
    16: "جراحة تجميلة",
    20: "سرطان و اورام"
}

r6 = client.get('/ios/specializations')
if r6.status_code == 200:
    specs = r6.json()
    all_match = True
    
    for spec_id, expected_name in swift_mapping.items():
        spec = next((s for s in specs if s['id'] == spec_id), None)
        if spec and spec['name'] == expected_name:
            print(f"   ✅ ID {spec_id:2d}: {expected_name}")
        else:
            print(f"   ❌ ID {spec_id:2d}: خطأ - {spec['name'] if spec else 'غير موجود'}")
            all_match = False
    
    if all_match:
        print(f"\n   ✅ جميع الاختصاصات متطابقة مع Swift!")
    else:
        print(f"\n   ❌ يوجد عدم تطابق")

print("\n" + "=" * 80)
print("✅ انتهى الاختبار")
print("=" * 80)
