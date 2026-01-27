# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext

# حمّل المتغيرات من .env (بدون الكتابة فوق الموجود)
load_dotenv(override=False)

# إعدادات الأمان من المتغيرات البيئية
SECRET_KEY = os.getenv("SECRET_KEY") or "dev-secret-change-me"
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# معالجة آمنة لقيم الوقت
try:
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
except (ValueError, TypeError):
    ACCESS_TOKEN_EXPIRE_MINUTES = 15

try:
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
except (ValueError, TypeError):
    REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__truncate_error=False  # لا ترمي خطأ عند كلمات المرور الطويلة
)


def get_password_hash(password: str) -> str:
    # تقليم كلمة المرور إلى 72 حرف (أكثر من كافي لـ 72 بايت)
    password = password[:72] if len(password) > 72 else password
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # تحويل كلمة المرور إلى bytes وقصها إلى 72 بايت (نفس الطريقة المستخدمة في التسجيل)
    password_bytes = plain_password.encode('utf-8')[:72]
    return pwd_context.verify(password_bytes, hashed_password)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(subject: str, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    jti = str(uuid.uuid4())
    expire = _now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": subject, "type": "access", "jti": jti, "exp": expire}
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token, "jti": jti, "exp": expire}


def create_refresh_token(subject: str, extra: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    jti = str(uuid.uuid4())
    expire = _now() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload: dict[str, Any] = {"sub": subject, "type": "refresh", "jti": jti, "exp": expire}
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"token": token, "jti": jti, "exp": expire}


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise e
