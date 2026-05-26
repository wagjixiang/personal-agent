"""OpenAI 客户端（兼容层，推荐使用 llm_api 替代）"""
# 此文件为了兼容性保留，建议切换到 llm_api.py

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL = os.getenv("GPT_MODEL", "qwen-plus")
MODEL_URL = os.getenv("MODEL_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=MODEL_URL,
)

__all__ = ['client', 'OPENAI_API_KEY', 'GPT_MODEL', 'MODEL_URL']
