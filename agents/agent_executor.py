"""Agent 执行引擎 - 核心的对话循环逻辑"""
import json
from typing import List, Dict, Any, Tuple

from logger import get_logger
from utils.json_utils import safe_json_loads, safe_json_dumps
from llm_api import chat_completion_request
from utils.tools import execute_tool, generate_openai_tools
from settings import settings

logger = get_logger(__name__)


# ============================================================
# Agent 执行器
# ============================================================

class AgentExecutor:
    """Agent 循环执行器 - 处理 LLM 响应和工具调用"""
    
    def __init__(self, max_tool_rounds: int = 5):
        """
        初始化 Agent 执行器
        
        参数：
            max_tool_rounds: 最大工具调用轮数
        """
        self.max_tool_rounds = max_tool_rounds
        logger.info(f"AgentExecutor initialized with max_tool_rounds={max_tool_rounds}")
    
    def run(
        self,
        conversation_history: List[Dict[str, Any]],
        default_answer: str = "抱歉，未能生成回答。"
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        执行 Agent 循环
        
        参数：
            conversation_history: 对话历史
            default_answer: 默认答案（当没有生成任何回复时）
        
        返回：
            (最终答案, 更新后的对话历史)
        """
        final_answer = default_answer
        
        for round_index in range(self.max_tool_rounds):
            logger.info(f"=== Agent Round {round_index + 1}/{self.max_tool_rounds} ===")
            
            # 调用 LLM
            try:
                response = chat_completion_request(
                    messages=conversation_history,
                    tools=generate_openai_tools()
                )
            except Exception as e:
                logger.exception(f"LLM request failed: {e}")
                final_answer = f"LLM 请求失败: {str(e)}"
                break
            
            message = response.choices[0].message
            
            # ========================================================
            # 情况 1: 没有工具调用，直接返回答案
            # ========================================================
            
            if not message.tool_calls:
                final_answer = message.content or default_answer
                conversation_history.append({
                    "role": "assistant",
                    "content": final_answer
                })
                logger.info(f"Agent completed without tool calls. Answer: {final_answer[:100]}...")
                break
            
            # ========================================================
            # 情况 2: 有工具调用，保存工具调用消息
            # ========================================================
            
            tool_calls_data = []
            for call in message.tool_calls:
                tool_calls_data.append({
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments
                    }
                })
            
            conversation_history.append({
                "role": "assistant",
                "tool_calls": tool_calls_data
            })
            logger.info(f"Tool calls: {[tc['function']['name'] for tc in tool_calls_data]}")
            
            # ========================================================
            # 执行所有工具调用
            # ========================================================
            
            for call in message.tool_calls:
                tool_name = call.function.name
                tool_args = safe_json_loads(call.function.arguments)
                
                logger.info(f"Executing tool: {tool_name}")
                logger.debug(f"Tool args: {tool_args}")
                
                # 执行工具
                try:
                    tool_result = execute_tool(tool_name=tool_name, arguments=tool_args)
                    logger.info(f"Tool result: {str(tool_result)[:200]}...")
                except Exception as e:
                    logger.exception(f"Tool execution exception: {e}")
                    tool_result = {
                        "success": False,
                        "error": str(e)
                    }
                
                # 保存工具结果
                conversation_history.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": safe_json_dumps(tool_result)
                })
        
        else:
            # 超过最大轮数
            final_answer = "工具调用次数过多，已停止。"
            conversation_history.append({
                "role": "assistant",
                "content": final_answer
            })
            logger.warning(f"Max tool rounds exceeded: {self.max_tool_rounds}")
        
        return final_answer, conversation_history
