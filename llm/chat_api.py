'''
Author: Wang Jixiang
Date: 2026-05-21 18:05:16
LastEditors: Wang Jixiang
LastEditTime: 2026-05-21 18:08:36
Description: 聊天agent api
'''
import json

from llm.client import client, GPT_MODEL


def get_answer(prompt, model: str = GPT_MODEL):
    """简单的问答接口，直接返回模型回复"""
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format={"type": "json_object"}
    )

    result = json.loads(
        completion.choices[0].message.content
    )

    return result


def chat_completion_request(messages, tools=[], model=GPT_MODEL):
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