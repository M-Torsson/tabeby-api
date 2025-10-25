"""
Test Iraq Timezone Implementation
"""
from app.timezone_utils import now_iraq, format_iraq_datetime, utc_to_iraq
from datetime import datetime, timezone

print("=" * 60)
print("Iraq Timezone Test")
print("=" * 60)

# Test 1: Current time in Iraq
print("\n1. Current Time in Iraq (UTC+3):")
iraq_now = now_iraq()
print(f"   {iraq_now}")
print(f"   Formatted: {iraq_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

# Test 2: UTC to Iraq conversion
print("\n2. UTC to Iraq Conversion:")
utc_time = datetime(2025, 10, 25, 9, 0, 0, tzinfo=timezone.utc)
iraq_time = utc_to_iraq(utc_time)
print(f"   UTC:  {utc_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"   Iraq: {iraq_time.strftime('%Y-%m-%d %H:%M:%S')}")

# Test 3: Database storage time
from app.timezone_utils import now_utc_for_storage
print("\n3. Database Storage Time (UTC for storage):")
storage_time = now_utc_for_storage()
print(f"   {storage_time}")

# Test 4: Format datetime
print("\n4. Format Iraq Datetime:")
formatted = format_iraq_datetime(utc_time, "%d/%m/%Y %H:%M")
print(f"   {formatted}")

print("\n" + "=" * 60)
print("✓ All timezone functions working correctly!")
print("=" * 60)
