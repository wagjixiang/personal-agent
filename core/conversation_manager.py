"""对话管理模块 - 管理会话和聊天历史

支持多种后端存储：
- MemorySessionStore：内存存储（开发用）
- RedisSessionStore：Redis 存储（生产用，分布式支持）
- DatabaseSessionStore：数据库存储（持久化）
"""

import uuid
import json
import logging
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
from datetime import datetime, timedelta

from logger import get_logger
from config.constants import SYSTEM_PROMPT

logger = get_logger(__name__)


# ============================================================
# 会话存储接口（支持扩展）
# ============================================================

class SessionStore(ABC):
    """会话存储抽象基类，支持多种后端实现（内存、Redis、数据库等）"""
    
    @abstractmethod
    def get(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """获取会话的聊天历史"""
        pass
    
    @abstractmethod
    def save(self, session_id: str, history: List[Dict[str, Any]]) -> None:
        """保存会话的聊天历史"""
        pass
    
    @abstractmethod
    def delete(self, session_id: str) -> None:
        """删除会话"""
        pass
    
    @abstractmethod
    def exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        pass


class MemorySessionStore(SessionStore):
    """基于内存的会话存储（开发用，生产环境建议使用 Redis/数据库）"""
    
    def __init__(self):
        self._store: Dict[str, tuple] = {}  # {session_id: (history, expires_at)}
        self.total_sessions = 0
    
    def get(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        if session_id not in self._store:
            return None
        
        history, expires_at = self._store[session_id]
        
        if datetime.now() > expires_at:
            del self._store[session_id]
            return None
        
        return history
    
    def save(self, session_id: str, history: List[Dict[str, Any]]) -> None:
        expires_at = datetime.now() + timedelta(hours=24)
        self._store[session_id] = (history, expires_at)
        self.total_sessions = len(self._store)
        logger.debug(f"Saved session: {session_id}")
    
    def delete(self, session_id: str) -> None:
        if session_id in self._store:
            del self._store[session_id]
            self.total_sessions = len(self._store)
            logger.info(f"Deleted session: {session_id}")
    
    def exists(self, session_id: str) -> bool:
        return session_id in self._store
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            'type': 'memory',
            'total_sessions': self.total_sessions,
            'size_bytes': sum(len(json.dumps(h)) for h, _ in self._store.values()),
        }


class RedisSessionStore(SessionStore):
    """基于 Redis 的会话存储（生产环境推荐）"""
    
    def __init__(self, redis_client, ttl_seconds: int = 86400):
        self.client = redis_client
        self.ttl_seconds = ttl_seconds
        self.key_prefix = "session:"
        logger.info("RedisSessionStore 初始化成功")
    
    def get(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        try:
            key = f"{self.key_prefix}{session_id}"
            value = self.client.get(key)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis GET 错误: {e}")
            return None
    
    def save(self, session_id: str, history: List[Dict[str, Any]]) -> None:
        try:
            key = f"{self.key_prefix}{session_id}"
            value = json.dumps(history, default=str)
            self.client.setex(key, self.ttl_seconds, value)
            logger.debug(f"Saved session to Redis: {session_id}")
        except Exception as e:
            logger.error(f"Redis SET 错误: {e}")
    
    def delete(self, session_id: str) -> None:
        try:
            key = f"{self.key_prefix}{session_id}"
            self.client.delete(key)
            logger.info(f"Deleted session from Redis: {session_id}")
        except Exception as e:
            logger.error(f"Redis DELETE 错误: {e}")
    
    def exists(self, session_id: str) -> bool:
        try:
            key = f"{self.key_prefix}{session_id}"
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Redis EXISTS 错误: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        try:
            info = self.client.info()
            return {
                'type': 'redis',
                'used_memory': info.get('used_memory_human', 'N/A'),
                'connected_clients': info.get('connected_clients', 0),
                'total_commands': info.get('total_commands_processed', 0),
            }
        except Exception as e:
            logger.error(f"Redis INFO 错误: {e}")
            return {}


# ============================================================
# 对话管理器
# ============================================================

class ConversationManager:
    """管理对话历史和会话"""
    
    def __init__(self, max_history: int = 20, store: Optional[SessionStore] = None):
        """
        初始化对话管理器
        
        参数：
            max_history: 保留的最大历史消息数
            store: 会话存储实现，默认使用内存存储
        """
        self.max_history = max_history
        self.store = store or MemorySessionStore()
        logger.info(f"ConversationManager initialized with max_history={max_history}")
    
    def create_conversation(self) -> List[Dict[str, Any]]:
        """
        创建新的空对话（包含系统提示）
        
        返回：
            新对话历史列表
        """
        return [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]
    
    def get_conversation(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取会话的对话历史，不存在则创建新的
        
        参数：
            session_id: 会话 ID
        
        返回：
            对话历史列表
        """
        history = self.store.get(session_id)
        
        if history is None:
            history = self.create_conversation()
            self.store.save(session_id, history)
            logger.info(f"Created new conversation: {session_id}")
        
        return history
    
    def save_conversation(self, session_id: str, history: List[Dict[str, Any]]) -> None:
        """
        保存对话历史
        
        参数：
            session_id: 会话 ID
            history: 对话历史
        """
        # 限制历史长度
        trimmed_history = self._trim_history(history)
        self.store.save(session_id, trimmed_history)
    
    def _trim_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        修剪历史消息，保留系统提示和最近的消息
        
        参数：
            history: 原始对话历史
        
        返回：
            修剪后的历史
        """
        if len(history) <= self.max_history + 1:
            return history
        
        # 保留系统消息（第一条）和最近的消息
        system_message = history[0]
        recent_messages = history[-(self.max_history):]
        
        trimmed = [system_message] + recent_messages
        logger.debug(f"Trimmed history from {len(history)} to {len(trimmed)} messages")
        
        return trimmed
    
    def add_user_message(self, session_id: str, message: str) -> None:
        """
        添加用户消息到对话历史
        
        参数：
            session_id: 会话 ID
            message: 用户消息内容
        """
        history = self.get_conversation(session_id)
        history.append({
            "role": "user",
            "content": message
        })
        self.save_conversation(session_id, history)
    
    def add_assistant_message(self, session_id: str, content: str) -> None:
        """
        添加助手消息到对话历史
        
        参数：
            session_id: 会话 ID
            content: 助手响应内容
        """
        history = self.get_conversation(session_id)
        history.append({
            "role": "assistant",
            "content": content
        })
        self.save_conversation(session_id, history)
    
    def add_tool_call_message(
        self,
        session_id: str,
        tool_calls: List[Dict[str, Any]]
    ) -> None:
        """
        添加工具调用消息
        
        参数：
            session_id: 会话 ID
            tool_calls: 工具调用列表
        """
        history = self.get_conversation(session_id)
        history.append({
            "role": "assistant",
            "tool_calls": tool_calls
        })
        self.save_conversation(session_id, history)
    
    def add_tool_result_message(
        self,
        session_id: str,
        tool_call_id: str,
        result: str
    ) -> None:
        """
        添加工具执行结果消息
        
        参数：
            session_id: 会话 ID
            tool_call_id: 工具调用 ID
            result: 执行结果（JSON 字符串）
        """
        history = self.get_conversation(session_id)
        history.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result
        })
        self.save_conversation(session_id, history)
    
    def delete_session(self, session_id: str) -> None:
        """
        删除会话
        
        参数：
            session_id: 会话 ID
        """
        self.store.delete(session_id)
    
    def get_store_stats(self) -> Dict[str, Any]:
        """获取存储后端统计信息"""
        return self.store.get_stats()
    
    @staticmethod
    def generate_session_id() -> str:
        """生成新的会话 ID"""
        return str(uuid.uuid4())
