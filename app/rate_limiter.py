# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


import time
from collections import defaultdict
from typing import Dict, List
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate Limiter بسيط في الذاكرة"""
    
    def __init__(self, requests: int = 100, window: int = 60):
        """
        Args:
            requests: عدد الطلبات المسموحة
            window: نافذة الوقت بالثواني (افتراضي: دقيقة واحدة)
        """
        self.requests = requests
        self.window = window
        self._cache: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.time()
    
    def is_allowed(self, key: str) -> bool:
        """التحقق من السماح للطلب"""
        now = time.time()
        
        self._cleanup_old_entries()
        
        self._cache[key] = [
            timestamp for timestamp in self._cache[key]
            if now - timestamp < self.window
        ]
        
        if len(self._cache[key]) >= self.requests:
            return False
        
        self._cache[key].append(now)
        return True
    
    def get_remaining(self, key: str) -> int:
        """الحصول على عدد الطلبات المتبقية"""
        now = time.time()
        recent_requests = [
            ts for ts in self._cache.get(key, [])
            if now - ts < self.window
        ]
        return max(0, self.requests - len(recent_requests))
    
    def get_reset_time(self, key: str) -> int:
        """الحصول على وقت إعادة تعيين العداد (Unix timestamp)"""
        now = time.time()
        recent_requests = self._cache.get(key, [])
        if not recent_requests:
            return int(now)
        
        oldest_request = min(recent_requests)
        return int(oldest_request + self.window)
    
    def _cleanup_old_entries(self):
        """تنظيف الإدخالات القديمة (كل 5 دقائق)"""
        now = time.time()
        if now - self._last_cleanup < 300:  # 5 دقائق
            return
        
        keys_to_delete = []
        for key, timestamps in self._cache.items():
            if not timestamps or (now - max(timestamps) > self.window * 2):
                keys_to_delete.append(key)
        
        for key in keys_to_delete:
            del self._cache[key]
        
        self._last_cleanup = now
        if keys_to_delete:
            logger.info(f"Rate Limiter CLEANUP: {len(keys_to_delete)} old entries removed")
    
    def stats(self) -> dict:
        """إحصائيات Rate Limiter"""
        return {
            "active_keys": len(self._cache),
            "requests_per_window": self.requests,
            "window_seconds": self.window
        }


default_limiter = RateLimiter(requests=300, window=60)    # 300 طلب/دقيقة للمسارات العادية
booking_limiter = RateLimiter(requests=200, window=60)    # 200 طلب/دقيقة للحجوزات
auth_limiter = RateLimiter(requests=30, window=60)        # 30 طلب/دقيقة للمصادقة


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware للـ Rate Limiting على مستوى التطبيق"""
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        excluded_paths = ["/health", "/docs", "/openapi.json", "/redoc"]
        if any(request.url.path.startswith(path) for path in excluded_paths):
            return await call_next(request)
        
        if "/auth/" in request.url.path:
            limiter = auth_limiter
        elif any(x in request.url.path for x in ["/booking", "/patient_booking", "/golden_booking"]):
            limiter = booking_limiter
        else:
            limiter = default_limiter
        
        rate_key = f"{client_ip}:{request.url.path}"
        
        if not limiter.is_allowed(rate_key):
            reset_time = limiter.get_reset_time(rate_key)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Too many requests",
                    "message": "أنت تقوم بإرسال طلبات كثيرة جداً. يرجى الانتظار قليلاً.",
                    "retry_after": reset_time - int(time.time())
                }
            )
        
        response = await call_next(request)
        
        remaining = limiter.get_remaining(rate_key)
        reset_time = limiter.get_reset_time(rate_key)
        
        response.headers["X-RateLimit-Limit"] = str(limiter.requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response


def rate_limit(requests: int = 100, window: int = 60):
    """
    ديكوريتر لإضافة Rate Limiting لـ endpoint معين
    
    مثال:
        @app.get("/api/data")
        @rate_limit(requests=50, window=60)
        def get_data():
            return {"data": "..."}
    """
    limiter = RateLimiter(requests=requests, window=window)
    
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            client_ip = request.client.host if request.client else "unknown"
            
            if not limiter.is_allowed(client_ip):
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again later."
                )
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator
