import json
from flask import Flask, render_template, request, jsonify

from server.llm_server import chat_completion_request
from utils.tools import get_current_time, find_point, generate_openai_tools

app = Flask(__name__)


# 全局变量存储对话历史
conversation_history = [
    {
        "role": "assistant",
        "content": """你是一个私人化的AI助手，名字是茉莉。你需要与用户进行持续的多轮对话，直到用户明确表示想要结束对话。

        对话规则：
        1. 请以御姐的语气回答问题，中文回答；
        2. 如果用户希望你帮他发送一封邮件，如果他没有提供发件人邮箱、收件人邮箱、邮件主题和邮件内容，请提示用户提供这些信息；
        3. 如果用户希望你帮他查找某个点距离数据库中最近的点，请提示用户提供目标点的坐标，格式为 [x, y]；
        4. 在每轮对话中，保持对话的连贯性，记住之前的对话内容;
        5. 如果用户表达以下意图，请结束对话：
        - 明确说"再见"、"拜拜"、"结束对话"等告别语
        - 表达"我要走了"、"对话到此为止"等结束意图
        - 使用"exit"、"quit"等退出命令"""
    }
]


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    global conversation_history

    data = request.json
    user_message = data.get('message', '')

    # 检查用户是否想要结束对话
    if user_message.lower() in ['再见', '拜拜', '结束对话', 'exit', 'quit', '我要走了', '对话到此为止']:
        return jsonify({
            'response': '哼~我也不是很想和你聊天，再见！',
            'end_conversation': True
        })

    conversation_history.append({"role": "user", "content": user_message})

    response = chat_completion_request(
        messages=conversation_history,
        tools=generate_openai_tools(),
    )

    message = response.choices[0].message

    # 模型正常回复
    if message.content:
        
        content = message.content

        conversation_history.append({
            "role": "assistant",
            "content": content
        })

        return jsonify({
            "response": content,
            "end_conversation": False
        })
    
    # 模型调用工具
    if message.tool_calls:

        # 保存 assistant 的 tool call
        conversation_history.append({
            "role": "assistant",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments
                    }
                }
                for call in message.tool_calls
            ] # type: ignore
        })

        # 工具映射表
        AVAILABLE_TOOLS = {
            "get_current_time": get_current_time,
            "find_point": find_point,
        }

        # 执行所有工具
        for call in message.tool_calls:

            fn_name = call.function.name

            fn_args = json.loads(
                call.function.arguments
            )

            # 获取函数
            fn = AVAILABLE_TOOLS[fn_name]

            # 执行函数
            tool_result = fn(**fn_args)

            # 保存 tool 返回结果
            conversation_history.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": str(tool_result)
            })

        # 再次请求LLM
        second_response = chat_completion_request(
            messages=conversation_history,
            tools=generate_openai_tools()
        )

        final_content = second_response.choices[0].message.content

        conversation_history.append({
            "role": "assistant",
            "content": final_content
        })

        return jsonify({
            "response": final_content,
            "end_conversation": False
        })


if __name__ == "__main__":
    app.run(debug=True)
