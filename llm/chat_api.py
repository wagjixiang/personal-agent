"""聊天API（兼容层，推荐使用 llm_api 替代）"""
# 此文件为了兼容性保留，建议切换到 llm_api.py

from llm_api import get_answer, chat_completion_request

__all__ = ['get_answer', 'chat_completion_request']
