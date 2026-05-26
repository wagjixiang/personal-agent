import json
import uuid
from utils.logger import get_logger
from typing import Dict, List, Any

from flask import Flask, render_template, request, jsonify

from llm.chat_api import chat_completion_request
from utils.tools import generate_openai_tools, execute_tool

# =========================================================
# Flask App
# =========================================================

app = Flask(__name__)

# =========================================================
# Config
# =========================================================

MAX_HISTORY = 20
MAX_TOOL_ROUNDS = 5

# =========================================================
# Session Memory Store
# 实际生产建议:
# Redis / MySQL / MongoDB
# =========================================================

conversation_store: Dict[str, List[Dict[str, Any]]] = {}

# =========================================================
# System Prompt
# =========================================================

SYSTEM_PROMPT = """
                    你是一个严谨的 AI 数据助手。

                    规则：

                    1. 如果问题涉及数据库中的真实数据：
                    必须调用 select_tool 查询数据库。

                    2. 不允许猜测数据库内容。

                    3. 不允许伪造统计结果。

                    4. 如果用户的问题涉及：
                    订单、销售额、库存、用户数据、统计信息、时间范围查询，
                    必须优先调用数据库工具。

                    5. 只有常识类问题才能直接回答。

                    6. 工具返回后，需要基于工具结果生成最终答案。

                    7. 使用中文简洁回答。

                    8. 如果工具执行失败：
                    明确告诉用户失败原因。
                """

# =========================================================
# Utils
# =========================================================

def create_new_conversation():
    return [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]


def get_conversation(session_id: str):
    if session_id not in conversation_store:
        conversation_store[session_id] = create_new_conversation()

    return conversation_store[session_id]


def trim_history(history: List[Dict[str, Any]]):

    # 保留 system prompt
    system_message = history[0]

    recent_history = history[-MAX_HISTORY:]

    return [system_message] + recent_history


def safe_json_loads(json_str: str, logger):

    try:
        return json.loads(json_str)

    except Exception as e:

        logger.error(f"JSON parse error: {e}")

        return {}


# =========================================================
# Home
# =========================================================

@app.route('/')
def home():
    return render_template('index.html')


# =========================================================
# Chat API
# =========================================================

@app.route('/chat', methods=['POST'])
def chat():
    logger = get_logger(__name__)

    try:

        data = request.json

        user_message = data.get("message", "").strip()

        # 前端不传则自动生成
        session_id = data.get("session_id")

        if not session_id:
            session_id = str(uuid.uuid4())

        # 获取会话
        conversation_history = get_conversation(session_id)

        # =================================================
        # 结束对话
        # =================================================

        if user_message.lower() in [
            "再见",
            "拜拜",
            "结束对话",
            "exit",
            "quit",
            "我要走了",
            "对话到此为止"
        ]:

            return jsonify({
                "response": "再见！",
                "session_id": session_id,
                "end_conversation": True
            })

        # =================================================
        # 添加用户消息
        # =================================================

        conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # =================================================
        # Agent Loop
        # =================================================

        final_answer = "抱歉，未能生成回答。"

        for round_index in range(MAX_TOOL_ROUNDS):

            logger.info(f"Agent Round: {round_index + 1}")

            response = chat_completion_request(
                messages=conversation_history,
                tools=generate_openai_tools()
            )

            message = response.choices[0].message

            # =================================================
            # 没有工具调用
            # =================================================

            if not message.tool_calls:

                final_answer = message.content or "未生成有效回复"

                conversation_history.append({
                    "role": "assistant",
                    "content": final_answer
                })

                break

            # =================================================
            # 保存 assistant tool call
            # =================================================

            assistant_tool_message = {
                "role": "assistant",
                "tool_calls": []
            }

            for call in message.tool_calls:

                assistant_tool_message["tool_calls"].append({
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments
                    }
                })

            conversation_history.append(assistant_tool_message)

            # =================================================
            # 执行 Tool Calls
            # =================================================

            for call in message.tool_calls:

                tool_name = call.function.name

                tool_args = safe_json_loads(
                    call.function.arguments,
                    logger
                )

                logger.info(f"Executing Tool => {tool_name}")

                logger.info(f"Tool Args => {tool_args}")

                # =============================================
                # 执行工具
                # =============================================

                try:

                    tool_result = execute_tool(tool_name=tool_name, arguments=tool_args)

                    logger.info(f"Tool Result => {tool_result}")

                except Exception as e:

                    logger.exception("Tool Execute Error")

                    tool_result = {
                        "success": False,
                        "error": str(e)
                    }

                # =============================================
                # 保存 Tool 返回
                # =============================================

                conversation_history.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(
                        tool_result,
                        ensure_ascii=False
                    )
                })

        else:

            final_answer = "工具调用次数过多，已停止。"

            conversation_history.append({
                "role": "assistant",
                "content": final_answer
            })

        # =================================================
        # 限制历史长度
        # =================================================

        conversation_store[session_id] = trim_history(conversation_history)

        # =================================================
        # 返回结果
        # =================================================

        return jsonify({
            "response": final_answer,
            "session_id": session_id,
            "end_conversation": False
        })

    except Exception as e:

        logger.exception("Chat API Error")

        return jsonify({
            "response": f"系统异常: {str(e)}",
            "end_conversation": False
        }), 500


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )