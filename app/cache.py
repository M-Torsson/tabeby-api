# Author: Muthana
# © 2026 Muthana. All rights reserved.
# Unauthorized copying or distribution is prohibited.


import json
import time
import hashlib
from typing import Optional, Any, Dict
from functools import wraps
import logging



class SimpleCache:
    """نظام كاش بسيط في الذاكرة (Memory Cache)"""
    
    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        """
        Args:
            default_ttl: مدة الصلاحية الافتراضية بالثواني (5 دقائق)
            max_size: الحد الأقصى لعدد العناصر في الكاش
        """
        self._cache: Dict[str, tuple[Any, float]] = {}
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._hits = 0
        self._misses = 0
        self._last_cleanup = time.time()
    
    def get(self, key: str) -> Optional[Any]:
        """الحصول على قيمة من الكاش"""
        self._cleanup_expired()
        
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                self._hits += 1
                return value
            else:
                del self._cache[key]
        
        self._misses += 1
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """حفظ قيمة في الكاش"""
        ttl = ttl or self.default_ttl
        expiry = time.time() + ttl
        
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        self._cache[key] = (value, expiry)
    
    def delete(self, key: str):
        """حذف قيمة من الكاش"""
        if key in self._cache:
            del self._cache[key]
    
    def delete_pattern(self, pattern: str):
        """حذف جميع المفاتيح التي تحتوي على النمط"""
        keys_to_delete = [k for k in self._cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self._cache[key]
    
    def clear(self):
        """مسح الكاش بالكامل"""
        size = len(self._cache)
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def _cleanup_expired(self):
        """تنظيف العناصر المنتهية (كل 60 ثانية)"""
        now = time.time()
        if now - self._last_cleanup < 60:
            return
        
        expired_keys = [
            key for key, (_, expiry) in self._cache.items()
            if now >= expiry
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        self._last_cleanup = now
        if expired_keys:
            logger.info(f"Cache CLEANUP: {len(expired_keys)} expired keys removed")
    
    def _evict_oldest(self):
        """حذف أقدم عنصر عند امتلاء الكاش"""
        if not self._cache:
            return
        
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
        del self._cache[oldest_key]
    
    def stats(self) -> dict:
        """إحصائيات الكاش"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "max_size": self.max_size,
            "usage": f"{(len(self._cache) / self.max_size * 100):.1f}%"
        }


cache = SimpleCache(
    default_ttl=60,
    max_size=10000
)


def cache_key(*args, **kwargs) -> str:
    """إنشاء مفتاح كاش فريد من المعاملات"""
    try:
        key_data = json.dumps(
            {"args": args, "kwargs": kwargs},
            sort_keys=True,
            default=str
        )
        return hashlib.md5(key_data.encode()).hexdigest()
    except Exception:
        return hashlib.md5(str((args, kwargs)).encode()).hexdigest()


def cached(ttl: int = 60, key_prefix: str = ""):
    """
    ديكوريتر للكاش التلقائي
    
    مثال:
        @cached(ttl=30, key_prefix="booking")
        def get_bookings(clinic_id: int):
            return db.query(...).all()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{key_prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"
            
            cached_value = cache.get(key)
            if cached_value is not None:
                return cached_value
            
            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        
        return wrapper
    return decorator


def invalidate_cache(key_pattern: str):
    """
    حذف الكاش بناءً على نمط معين
    
    مثال:
        invalidate_cache("booking:clinic:7")
    """
    cache.delete_pattern(key_pattern)
