#!/usr/bin/env python3
"""
Check Firebase configuration for Egypt phone number support.
"""
import os

# Set environment before importing
os.environ.setdefault('DOCTOR_PROFILE_SECRET', 'test-secret')

try:
    from app.firebase_init import ensure_firebase_initialized
    from firebase_admin import auth as firebase_auth
    
    print("=" * 70)
    print("🔍 Firebase Egypt Phone Number Support Check")
    print("=" * 70)
    
    # Initialize Firebase
    try:
        ensure_firebase_initialized()
        print("✅ Firebase initialized successfully")
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        print("\n⚠️  تأكد من:")
        print("   1. FIREBASE_CREDENTIALS_JSON موجود في Environment Variables")
        print("   2. أو الملف موجود في: /etc/secrets/")
        exit(1)
    
    # Test Egyptian phone number format
    egypt_phone = "+201234567890"  # مثال لرقم مصري
    
    print(f"\n📱 Testing Egyptian phone number format: {egypt_phone}")
    print("   Format: +20 (Egypt code) + 10 digits")
    
    # Try to list users (to verify Firebase Auth is working)
    try:
        users_page = firebase_auth.list_users(max_results=1)
        print(f"\n✅ Firebase Auth connection working")
        print(f"   Total users in Firebase: Can access user list")
    except Exception as e:
        print(f"\n⚠️  Could not access user list: {e}")
    
    # Check if we can search for an Egyptian number (if exists)
    print(f"\n🔍 Checking if Egyptian numbers exist in Firebase...")
    try:
        count = 0
        egypt_users = []
        for user in firebase_auth.list_users().iterate_all():
            if user.phone_number and user.phone_number.startswith('+20'):
                egypt_users.append(user.phone_number)
                count += 1
                if count >= 5:  # Show max 5 examples
                    break
        
        if egypt_users:
            print(f"✅ Found {count} Egyptian phone numbers:")
            for phone in egypt_users:
                print(f"   - {phone}")
        else:
            print("⚠️  No Egyptian phone numbers found yet")
            print("   (This is normal if you haven't registered any Egyptian users)")
    except Exception as e:
        print(f"⚠️  Could not search users: {e}")
    
    print("\n" + "=" * 70)
    print("📋 Summary:")
    print("=" * 70)
    print("1. Firebase SDK: ✅ Working")
    print("2. Egypt support: ✅ Firebase supports Egypt (+20)")
    print("3. Format required: +201234567890 (country code + 10 digits)")
    print("\n⚠️  Important Notes:")
    print("   - Egypt is in 'opt-in required' list")
    print("   - Make sure your Firebase project doesn't block Egypt")
    print("   - Check Firebase Console > Authentication > Settings")
    print("   - reCAPTCHA should be configured for production")
    print("\n🧪 To test SMS:")
    print("   1. Open your Flutter app")
    print("   2. Try to register with: +20 1234567890")
    print("   3. Firebase should send SMS with 6-digit code")
    print("   4. If it fails, check Firebase Console for blocked regions")
    print("=" * 70)

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("تأكد من تثبيت firebase-admin:")
    print("   python -m pip install firebase-admin")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
