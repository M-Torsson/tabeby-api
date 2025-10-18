"""
اختبار تحسينات الكاش الجديدة
"""
from fastapi.testclient import TestClient
from app.main import app
from app.cache import cache
import time

client = TestClient(app)

print("=" * 60)
print("اختبار تحسينات الكاش")
print("=" * 60)

# مسح الكاش قبل البدء
cache.clear()
print("\n1️⃣ مسح الكاش...")
stats = cache.stats()
print(f"   ✓ الإحصائيات بعد المسح: {stats}")

# أول طلب - يجب أن يكون cache miss
print("\n2️⃣ الطلب الأول (يجب أن يكون cache miss)...")
r1 = client.get('/api/doctors?page=1&pageSize=10')
print(f"   Status: {r1.status_code}")
print(f"   Items: {len(r1.json().get('items', []))}")
stats_after_1 = cache.stats()
print(f"   Cache Stats: Hits={stats_after_1['hits']}, Misses={stats_after_1['misses']}")

# الطلب الثاني - يجب أن يكون cache hit
print("\n3️⃣ الطلب الثاني - نفس المعاملات (يجب أن يكون cache hit)...")
time.sleep(0.5)  # انتظار قليل
r2 = client.get('/api/doctors?page=1&pageSize=10')
print(f"   Status: {r2.status_code}")
print(f"   Items: {len(r2.json().get('items', []))}")
stats_after_2 = cache.stats()
print(f"   Cache Stats: Hits={stats_after_2['hits']}, Misses={stats_after_2['misses']}")

# الطلب الثالث - معاملات مختلفة (cache miss)
print("\n4️⃣ الطلب الثالث - معاملات مختلفة (يجب أن يكون cache miss)...")
r3 = client.get('/api/doctors?page=2&pageSize=10')
print(f"   Status: {r3.status_code}")
print(f"   Items: {len(r3.json().get('items', []))}")
stats_after_3 = cache.stats()
print(f"   Cache Stats: Hits={stats_after_3['hits']}, Misses={stats_after_3['misses']}")

# الطلب الرابع - نفس المعاملات الثالثة (cache hit)
print("\n5️⃣ الطلب الرابع - نفس المعاملات السابقة (يجب أن يكون cache hit)...")
r4 = client.get('/api/doctors?page=2&pageSize=10')
print(f"   Status: {r4.status_code}")
stats_after_4 = cache.stats()
print(f"   Cache Stats: Hits={stats_after_4['hits']}, Misses={stats_after_4['misses']}")

# الطلب الخامس - العودة للأول (cache hit)
print("\n6️⃣ الطلب الخامس - العودة للطلب الأول (يجب أن يكون cache hit)...")
r5 = client.get('/api/doctors?page=1&pageSize=10')
print(f"   Status: {r5.status_code}")
stats_after_5 = cache.stats()
print(f"   Cache Stats: Hits={stats_after_5['hits']}, Misses={stats_after_5['misses']}")

# حساب Hit Rate النهائي
total = stats_after_5['hits'] + stats_after_5['misses']
hit_rate = (stats_after_5['hits'] / total * 100) if total > 0 else 0

print("\n" + "=" * 60)
print("📊 النتيجة النهائية:")
print(f"   Total Requests: {total}")
print(f"   Hits: {stats_after_5['hits']} ✓")
print(f"   Misses: {stats_after_5['misses']} ✗")
print(f"   Hit Rate: {hit_rate:.2f}%")
print(f"   Cache Size: {stats_after_5['size']}")
print(f"   Cache Usage: {stats_after_5['usage']}")

if hit_rate >= 50:
    print("\n   ✅ ممتاز! الكاش يعمل بشكل جيد!")
elif hit_rate >= 30:
    print("\n   ⚠️  جيد، لكن يمكن تحسينه")
else:
    print("\n   ❌ الأداء ضعيف - يحتاج تحسين")

print("=" * 60)
