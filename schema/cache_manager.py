"""
缓存管理器 - LRU缓存用于表推断结果

用途：
1. 缓存用户查询到表推断的结果
2. 避免重复计算相同查询
3. 支持TTL过期机制
"""

from collections import OrderedDict
from typing import List, Optional
from datetime import datetime, timedelta


class LRUCache:
    """LRU缓存实现"""
    
    def __init__(self, max_size: int = 500, ttl_minutes: int = 60):
        """
        Args:
            max_size: 最大缓存条数
            ttl_minutes: 缓存过期时间（分钟）
        """
        self.max_size = max_size
        self.ttl = timedelta(minutes=ttl_minutes)
        self.cache = OrderedDict()
        self.timestamps = {}
    
    def get(self, key: str) -> Optional[any]:
        """获取缓存，如果过期则返回None"""
        if key not in self.cache:
            return None
        
        # 检查是否过期
        if datetime.now() - self.timestamps[key] > self.ttl:
            self.delete(key)
            return None
        
        # LRU: 将访问的项移到末尾
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def put(self, key: str, value: any) -> None:
        """存储缓存"""
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        self.timestamps[key] = datetime.now()
        
        # 如果超过最大容量，删除最老的项
        if len(self.cache) > self.max_size:
            oldest_key = next(iter(self.cache))
            self.delete(oldest_key)
    
    def delete(self, key: str) -> None:
        """删除缓存"""
        if key in self.cache:
            del self.cache[key]
            del self.timestamps[key]
    
    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()
        self.timestamps.clear()
    
    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl_minutes": self.ttl.total_seconds() / 60,
            "usage_percent": (len(self.cache) / self.max_size) * 100
        }


class CacheManager:
    """表推断缓存管理器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheManager, cls).__new__(cls)
            cls._instance.cache = LRUCache(max_size=500, ttl_minutes=60)
            cls._instance.hits = 0
            cls._instance.misses = 0
        return cls._instance
    
    def get_cached_tables(self, query: str) -> Optional[List[str]]:
        """获取缓存的表推断结果"""
        result = self.cache.get(query)
        if result is not None:
            self.hits += 1
        else:
            self.misses += 1
        return result
    
    def cache_tables(self, query: str, tables: List[str]) -> None:
        """缓存表推断结果"""
        self.cache.put(query, tables)
    
    def clear_cache(self) -> None:
        """清空所有缓存"""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "cache": self.cache.get_stats(),
            "hits": self.hits,
            "misses": self.misses,
            "total_requests": total_requests,
            "hit_rate_percent": hit_rate
        }


# 全局实例
def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    return CacheManager()
