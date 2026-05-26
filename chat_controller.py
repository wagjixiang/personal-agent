"""聊天控制器 - 处理 Flask 路由和 HTTP 请求"""
from typing import Dict, Any

from flask import Blueprint, request, jsonify

from logger import get_logger
from conversation_manager import ConversationManager
from agents.agent_executor import AgentExecutor
from constants import END_CONVERSATION_KEYWORDS, DEFAULT_FINAL_ANSWER
from settings import settings
from utils.json_utils import safe_json_dumps

logger = get_logger(__name__)

# 创建蓝图
chat_bp = Blueprint('chat', __name__)

# 全局的对话管理器和 Agent 执行器
conversation_manager = ConversationManager(max_history=settings.MAX_HISTORY)
agent_executor = AgentExecutor(max_tool_rounds=settings.MAX_TOOL_ROUNDS)


# ============================================================
# 聊天 API 路由
# ============================================================

@chat_bp.route('/chat', methods=['POST'])
def chat():
    """
    聊天接口
    
    请求体:
        {
            "message": "用户消息",
            "session_id": "会话ID (可选，不提供则自动生成)"
        }
    
    响应:
        {
            "response": "助手回复",
            "session_id": "会话ID",
            "end_conversation": false
        }
    """
    try:
        # 解析请求
        data = request.get_json(force=True) or {}
        user_message = data.get("message", "").strip()
        session_id = data.get("session_id")
        
        # 生成或使用提供的会话 ID
        if not session_id:
            session_id = ConversationManager.generate_session_id()
            logger.info(f"Generated new session: {session_id}")
        else:
            logger.info(f"Using existing session: {session_id}")
        
        # ====================================================
        # 检查对话结束关键词
        # ====================================================
        
        if user_message.lower() in END_CONVERSATION_KEYWORDS:
            logger.info(f"End conversation triggered by user: {session_id}")
            return jsonify({
                "response": "再见！",
                "session_id": session_id,
                "end_conversation": True
            })
        
        # ====================================================
        # 执行 Agent 循环
        # ====================================================
        
        # 添加用户消息到历史
        conversation_manager.add_user_message(session_id, user_message)
        
        # 获取当前对话历史
        conversation_history = conversation_manager.get_conversation(session_id)
        
        logger.info(f"Chat request: session={session_id}, message_len={len(user_message)}")
        
        # 运行 Agent
        final_answer, updated_history = agent_executor.run(
            conversation_history,
            default_answer=DEFAULT_FINAL_ANSWER
        )
        
        # 保存更新后的对话历史
        conversation_manager.save_conversation(session_id, updated_history)
        
        # ====================================================
        # 返回结果
        # ====================================================
        
        response_data = {
            "response": final_answer,
            "session_id": session_id,
            "end_conversation": False
        }
        
        logger.info(f"Chat response: session={session_id}, answer_len={len(final_answer)}")
        
        return jsonify(response_data)
    
    except Exception as e:
        logger.exception("Chat API Error")
        return jsonify({
            "response": f"系统异常: {str(e)}",
            "end_conversation": False
        }), 500


@chat_bp.route('/chat/history/<session_id>', methods=['GET'])
def get_history(session_id: str):
    """
    获取会话历史
    
    参数:
        session_id: 会话 ID
    
    响应:
        {
            "session_id": "会话ID",
            "history": [...]
        }
    """
    try:
        history = conversation_manager.get_conversation(session_id)
        return jsonify({
            "session_id": session_id,
            "history": history
        })
    except Exception as e:
        logger.exception("Get history error")
        return jsonify({"error": str(e)}), 500


@chat_bp.route('/chat/clear/<session_id>', methods=['DELETE'])
def clear_session(session_id: str):
    """
    清除会话
    
    参数:
        session_id: 会话 ID
    """
    try:
        conversation_manager.delete_session(session_id)
        logger.info(f"Cleared session: {session_id}")
        return jsonify({"message": "会话已清除"})
    except Exception as e:
        logger.exception("Clear session error")
        return jsonify({"error": str(e)}), 500
