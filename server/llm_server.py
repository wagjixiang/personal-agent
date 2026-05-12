'''
Author: Wang Jixiang
Date: 2026-05-12 16:09:43
LastEditors: Wang Jixiang
LastEditTime: 2026-05-12 17:07:02
Description: 
'''
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GPT_MODEL = os.getenv("GPT_MODEL")
MODEL_URL = os.getenv("MODEL_URL")

client = OpenAI(
    # 若没有配置环境变量，请用百炼API Key将下行替换为：api_key="sk-xxx",
    api_key=OPENAI_API_KEY,
    # 填写DashScope SDK的base_url
    base_url=MODEL_URL,
)


def chat_completion_request(messages, tools, model=GPT_MODEL):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
        )
        return response
    except Exception as e:
        print("Unable to generate ChatCompletion response")
        print(f"Exception: {e}")
        return e
    