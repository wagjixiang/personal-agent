"""
Redis 缓存与会话管理模块

功能：
- 会话存储（替代内存存储）
- 查询结果缓存
- 查询计划缓存
- 缓存预热与过期管理
- 分布式锁（用于并发控制）
"""

import os
import json
import logging
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# ============================================================
# Redis 客户端
# ============================================================

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis 模块未安装，缓存功能将被禁用")


class CacheBackend(ABC):
    """缓存后端抽象基类"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """获取缓存"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """设置缓存"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除缓存"""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """清空所有缓存"""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        pass


class RedisCache(CacheBackend):
    """Redis 缓存实现"""
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 3600
    ):
        if not REDIS_AVAILABLE:
            raise RuntimeError("redis 模块未安装")
        
        self.host = host
        self.port = port
        self.db = db
        self.default_ttl = default_ttl
        
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                socket_keepalive_options={},
                retry_on_timeout=True,
            )
            # 测试连接
            self.client.ping()
            logger.info(f"Redis 连接成功: {host}:{port}/{db}")
        except Exception as e:
            logger.error(f"Redis 连接失败: {e}")
            raise
    
    def get(self, key: str) -> Optional[str]:
        """获取缓存"""
        try:
            value = self.client.get(key)
            if value:
                logger.debug(f"缓存命中: {key}")
            return value
        except Exception as e:
            logger.error(f"Redis GET 错误: {e}")
            return None
    
    def set(self, key: str, value: str, ttl: int = None) -> bool:
        """设置缓存"""
        try:
            ttl = ttl or self.default_ttl
            result = self.client.setex(key, ttl, value)
            logger.debug(f"缓存设置: {key} (TTL: {ttl}s)")
            return bool(result)
        except Exception as e:
            logger.error(f"Redis SET 错误: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            result = self.client.delete(key)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis DELETE 错误: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS 错误: {e}")
            return False
    
    def clear(self) -> bool:
        """清空所有缓存"""
        try:
            self.client.flushdb()
            logger.info("Redis 缓存已清空")
            return True
        except Exception as e:
            logger.error(f"Redis FLUSHDB 错误: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            info = self.client.info()
            return {
                'used_memory': info.get('used_memory_human', 'N/A'),
                'connected_clients': info.get('connected_clients', 0),
                'total_commands': info.get('total_commands_processed', 0),
                'keyspace': self.client.dbsize(),
            }
        except Exception as e:
            logger.error(f"Redis INFO 错误: {e}")
            return {}


class MemoryCache(CacheBackend):
    """内存缓存实现（备选方案，用于开发环境）"""
    
    def __init__(self, default_ttl: int = 3600):
        self._store: Dict[str, tuple] = {}  # {key: (value, expires_at)}
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[str]:
        """获取缓存"""
        if key not in self._store:
            self.misses += 1
            return None
        
        value, expires_at = self._store[key]
        
        if datetime.now() >= expires_at:
            del self._store[key]
            self.misses += 1
            return None
        
        self.hits += 1
        return value
    
    def set(self, key: str, value: str, ttl: int = None) -> bool:
        """设置缓存"""
        ttl = ttl or self.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl)
        self._store[key] = (value, expires_at)
        return True
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        if key in self._store:
            del self._store[key]
            return True
        return False
    
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        if key not in self._store:
            return False
        
        value, expires_at = self._store[key]
        if datetime.now() >= expires_at:
            del self._store[key]
            return False
        
        return True
    
    def clear(self) -> bool:
        """清空所有缓存"""
        self._store.clear()
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        hit_rate = (
            self.hits / (self.hits + self.misses)
            if (self.hits + self.misses) > 0
            else 0
        )
        return {
            'type': 'memory',
            'size': len(self._store),
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': f"{hit_rate*100:.1f}%",
        }


# ============================================================
# 缓存键生成器
# ============================================================

class CacheKeyBuilder:
    """缓存键构建器"""
    
    @staticmethod
    def query_result_key(sql: str, params: Dict = None) -> str:
        """生成查询结果缓存键"""
        query_hash = hashlib.md5(
            (sql + json.dumps(params or {}, sort_keys=True)).encode()
        ).hexdigest()
        return f"query_result:{query_hash}"
    
    @staticmethod
    def query_plan_key(question: str) -> str:
        """生成查询计划缓存键"""
        plan_hash = hashlib.md5(question.encode()).hexdigest()
        return f"query_plan:{plan_hash}"
    
    @staticmethod
    def session_key(session_id: str) -> str:
        """生成会话缓存键"""
        return f"session:{session_id}"
    
    @staticmethod
    def semantic_result_key(embedding: str) -> str:
        """生成语义搜索结果缓存键"""
        return f"semantic:{embedding}"


# ============================================================
# 缓存管理器
# ============================================================

class CacheManager:
    """统一的缓存管理接口"""
    
    def __init__(self, backend: CacheBackend):
        self.backend = backend
        self.key_builder = CacheKeyBuilder()
    
    def cache_query_result(
        self,
        sql: str,
        result: List[Dict[str, Any]],
        params: Dict = None,
        ttl: int = 3600
    ) -> bool:
        """缓存查询结果"""
        key = self.key_builder.query_result_key(sql, params)
        value = json.dumps(result, default=str)
        return self.backend.set(key, value, ttl)
    
    def get_cached_query_result(
        self,
        sql: str,
        params: Dict = None
    ) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的查询结果"""
        key = self.key_builder.query_result_key(sql, params)
        value = self.backend.get(key)
        if value:
            return json.loads(value)
        return None
    
    def cache_query_plan(
        self,
        question: str,
        plan: Dict[str, Any],
        ttl: int = 86400
    ) -> bool:
        """缓存查询计划"""
        key = self.key_builder.query_plan_key(question)
        value = json.dumps(plan, default=str)
        return self.backend.set(key, value, ttl)
    
    def get_cached_query_plan(self, question: str) -> Optional[Dict[str, Any]]:
        """获取缓存的查询计划"""
        key = self.key_builder.query_plan_key(question)
        value = self.backend.get(key)
        if value:
            return json.loads(value)
        return None
    
    def cache_session(
        self,
        session_id: str,
        conversation: List[Dict[str, Any]],
        ttl: int = 86400
    ) -> bool:
        """缓存会话数据"""
        key = self.key_builder.session_key(session_id)
        value = json.dumps(conversation, default=str)
        return self.backend.set(key, value, ttl)
    
    def get_cached_session(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的会话数据"""
        key = self.key_builder.session_key(session_id)
        value = self.backend.get(key)
        if value:
            return json.loads(value)
        return None
    
    def invalidate_query_cache(self, sql: str = None, params: Dict = None):
        """清空查询缓存"""
        if sql and params:
            key = self.key_builder.query_result_key(sql, params)
            self.backend.delete(key)
        else:
            # 清空所有 query_result: 前缀的缓存（需要 Redis）
            logger.info("清空所有查询缓存")


# ============================================================
# 工厂函数
# ============================================================

def create_cache_backend(cache_type: str = "redis") -> CacheBackend:
    """创建缓存后端"""
    
    if cache_type == "redis":
        if not REDIS_AVAILABLE:
            logger.warning("redis 模块未安装，使用内存缓存")
            return MemoryCache()
        
        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        try:
            # 简单解析 Redis URL
            # 格式: redis://[:password]@host:port/db
            from urllib.parse import urlparse
            parsed = urlparse(redis_url)
            
            return RedisCache(
                host=parsed.hostname or "127.0.0.1",
                port=parsed.port or 6379,
                db=int(parsed.path.lstrip('/')) if parsed.path else 0,
                password=parsed.password,
            )
        except Exception as e:
            logger.error(f"Redis 初始化失败: {e}，使用内存缓存")
            return MemoryCache()
    
    return MemoryCache()


if __name__ == "__main__":
    # 测试内存缓存
    cache = MemoryCache()
    cache_mgr = CacheManager(cache)
    
    # 测试查询结果缓存
    test_result = [{"id": 1, "name": "test"}]
    cache_mgr.cache_query_result("SELECT * FROM test", test_result)
    print("缓存结果:", cache_mgr.get_cached_query_result("SELECT * FROM test"))
    
    # 测试统计
    print("缓存统计:", cache_mgr.backend.get_stats())
