"""对话管理模块 - 管理会话和聊天历史"""
import uuid
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

from logger import get_logger
from constants import SYSTEM_PROMPT

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


class MemorySessionStore(SessionStore):
    """基于内存的会话存储（开发用，生产环境建议使用 Redis/数据库）"""
    
    def __init__(self):
        self._store: Dict[str, List[Dict[str, Any]]] = {}
    
    def get(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        return self._store.get(session_id)
    
    def save(self, session_id: str, history: List[Dict[str, Any]]) -> None:
        self._store[session_id] = history
    
    def delete(self, session_id: str) -> None:
        if session_id in self._store:
            del self._store[session_id]
            logger.info(f"Deleted session: {session_id}")
    
    def exists(self, session_id: str) -> bool:
        return session_id in self._store


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
    
    @staticmethod
    def generate_session_id() -> str:
        """生成新的会话 ID"""
        return str(uuid.uuid4())
