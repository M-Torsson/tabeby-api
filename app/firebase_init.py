# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


import os, json
try:
    import firebase_admin
    from firebase_admin import credentials
except Exception:
    firebase_admin = None
    credentials = None


def ensure_firebase_initialized() -> None:
    """Initialize Firebase Admin SDK from either:
    - FIREBASE_CREDENTIALS_JSON (full JSON string), or
    - FIREBASE_CREDENTIALS_PATH (file path, e.g. /etc/secrets/xxx.json)
    """
    if not firebase_admin or not credentials:
        raise RuntimeError("firebase_admin package not installed")

    if firebase_admin._apps:
        return

    creds_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if creds_json:
        try:
            data = json.loads(creds_json)
        except json.JSONDecodeError as e:
            raise RuntimeError("FIREBASE_CREDENTIALS_JSON is not valid JSON") from e
        cred = credentials.Certificate(data)
        firebase_admin.initialize_app(cred)
        return

    creds_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
    if creds_path and os.path.exists(creds_path):
        cred = credentials.Certificate(creds_path)
        firebase_admin.initialize_app(cred)
        return

    default_path = "/etc/secrets/tabeby-auth-firebase-adminsdk-fbsvc-46d417a54c.json"
    if os.path.exists(default_path):
        cred = credentials.Certificate(default_path)
        firebase_admin.initialize_app(cred)
        return

    raise RuntimeError(
        "Firebase credentials not provided. Set FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH."
    )
