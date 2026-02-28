from typing import Any, Optional
from datetime import datetime, timedelta
import hashlib


class CacheManager:
    _instance = None
    _cache: dict = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get(self, key: str) -> Optional[Any]:
        item = self._cache.get(key)
        if item is None:
            return None
        
        if datetime.now() > item['expires_at']:
            del self._cache[key]
            return None
        
        return item['value']
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        self._cache[key] = {
            'value': value,
            'expires_at': datetime.now() + timedelta(seconds=ttl_seconds)
        }
    
    def delete(self, key: str):
        if key in self._cache:
            del self._cache[key]
    
    def clear(self):
        self._cache.clear()
    
    @staticmethod
    def generate_key(*args) -> str:
        key_str = '|'.join(str(arg) for arg in args)
        return hashlib.md5(key_str.encode()).hexdigest()
