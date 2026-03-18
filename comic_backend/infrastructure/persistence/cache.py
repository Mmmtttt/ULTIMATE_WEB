from typing import Any, Optional
from datetime import datetime, timedelta
import hashlib
import json
import os
from core.constants import CACHE_ROOT_DIR


CACHE_DIR = CACHE_ROOT_DIR


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

    def _build_persistent_filepath(self, key: str, category: str = 'default') -> str:
        raw_key = str(key or "")
        key_hash = hashlib.md5(raw_key.encode("utf-8")).hexdigest()
        return os.path.join(CACHE_DIR, f"{category}_{key_hash}.json")

    def _build_legacy_persistent_filepath(self, key: str, category: str = 'default') -> str:
        return os.path.join(CACHE_DIR, f"{category}_{key}.json")
    
    def get_persistent(self, key: str, category: str = 'default') -> Optional[Any]:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            filepath = self._build_persistent_filepath(key, category)
            legacy_filepath = self._build_legacy_persistent_filepath(key, category)

            data = None
            active_path = None
            for candidate in (filepath, legacy_filepath):
                if not os.path.exists(candidate):
                    continue
                with open(candidate, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                active_path = candidate
                break

            if data is None:
                return None
            
            expires_at_str = data.get('expires_at', '')
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                if datetime.now() > expires_at:
                    if active_path and os.path.exists(active_path):
                        os.remove(active_path)
                    return None
            
            return data.get('value')
        except Exception:
            return None
    
    def set_persistent(self, key: str, value: Any, category: str = 'default', ttl_seconds: int = None):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            filepath = self._build_persistent_filepath(key, category)
            
            expires_at = None
            if ttl_seconds is not None and ttl_seconds > 0:
                expires_at = (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat()
            
            data = {
                'value': value,
                'expires_at': expires_at
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def delete_persistent(self, key: str, category: str = 'default') -> bool:
        try:
            deleted = False
            for filepath in (
                self._build_persistent_filepath(key, category),
                self._build_legacy_persistent_filepath(key, category),
            ):
                if os.path.exists(filepath):
                    os.remove(filepath)
                    deleted = True
            return deleted
        except Exception:
            return False
    
    def clear_persistent_category(self, category: str) -> int:
        count = 0
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            for filename in os.listdir(CACHE_DIR):
                if filename.startswith(f"{category}_"):
                    filepath = os.path.join(CACHE_DIR, filename)
                    os.remove(filepath)
                    count += 1
        except Exception:
            pass
        return count
