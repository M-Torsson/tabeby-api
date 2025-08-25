import os, json
try:
    import firebase_admin  # type: ignore
    from firebase_admin import credentials  # type: ignore
except Exception:  # pragma: no cover
    firebase_admin = None  # type: ignore
    credentials = None  # type: ignore


def ensure_firebase_initialized() -> None:
    """Initialize Firebase Admin SDK from either:
    - FIREBASE_CREDENTIALS_JSON (full JSON string), or
    - FIREBASE_CREDENTIALS_PATH (file path, e.g. /etc/secrets/xxx.json)
    """
    if not firebase_admin or not credentials:
        raise RuntimeError("firebase_admin package not installed")

    if firebase_admin._apps:
        return

    # 1) جرّب JSON من متغيّر البيئة
    creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if creds_json:
        try:
            data = json.loads(creds_json)
        except json.JSONDecodeError as e:
            raise RuntimeError("FIREBASE_CREDENTIALS_JSON is not valid JSON") from e
        cred = credentials.Certificate(data)
        firebase_admin.initialize_app(cred)
        return

    # 2) جرّب ملف من مسار
    creds_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
    if creds_path and os.path.exists(creds_path):
        cred = credentials.Certificate(creds_path)
        firebase_admin.initialize_app(cred)
        return

    # 3) (اختياري) مسار Render الافتراضي لو رفعت الملف كـ Secret File
    # استبدل الاسم بالاسم الحقيقي للملف الذي يظهر لك في لوحة Render
    default_path = "/etc/secrets/tabeby-auth-firebase-adminsdk-fbsvc-46d417a54c.json"
    if os.path.exists(default_path):
        cred = credentials.Certificate(default_path)
        firebase_admin.initialize_app(cred)
        return

    raise RuntimeError(
        "Firebase credentials not provided. Set FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH."
    )
