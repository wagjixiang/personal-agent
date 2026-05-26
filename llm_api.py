"""统一的 LLM API 接口（合并 client.py 和 chat_api.py）"""
import json
import os
from typing import Optional, List, Dict, Any

from openai import OpenAI
from dotenv import load_dotenv

from logger import get_logger
from exceptions import LLMException

# 加载环境变量
load_dotenv()

logger = get_logger(__name__)

# ============================================================
# LLM 客户端初始化
# ============================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL = os.getenv("GPT_MODEL", "qwen-plus")
MODEL_URL = os.getenv("MODEL_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

# 验证必要配置
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY 环境变量未设置")

if not MODEL_URL:
    logger.error("MODEL_URL 环境变量未设置")

# 初始化 OpenAI 客户端
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=MODEL_URL,
)


# ============================================================
# LLM API 接口
# ============================================================

def get_answer(
    prompt: str,
    model: str = GPT_MODEL,
    response_format: Optional[Dict[str, Any]] = None
) -> Any:
    """
    简单的问答接口，直接返回模型回复
    
    参数：
        prompt: 用户提示词
        model: 使用的模型名称
        response_format: 响应格式设置（默认 JSON）
    
    返回：
        模型的回复内容（JSON 格式）
    """
    if response_format is None:
        response_format = {"type": "json_object"}
    
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            response_format=response_format
        )
        
        # 解析 JSON 响应
        result = json.loads(completion.choices[0].message.content)
        logger.info(f"LLM get_answer success: model={model}")
        return result
        
    except Exception as e:
        logger.exception(f"LLM get_answer error: {e}")
        raise LLMException(f"获取答案失败: {str(e)}")


def chat_completion_request(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    model: str = GPT_MODEL
) -> Any:
    """
    聊天完成请求，支持 tool calling
    
    参数：
        messages: 消息历史
        tools: 可用工具列表
        model: 使用的模型名称
    
    返回：
        模型响应对象
    """
    try:
        request_params = {
            "model": model,
            "messages": messages,
        }
        
        if tools:
            request_params["tools"] = tools
        
        response = client.chat.completions.create(**request_params)
        logger.info(f"LLM chat_completion_request success: model={model}")
        return response
        
    except Exception as e:
        logger.exception(f"LLM chat_completion_request error: {e}")
        raise LLMException(f"聊天完成请求失败: {str(e)}")
