import json
from flask import Flask, render_template, request, jsonify

from server.llm_server import chat_completion_request
from utils.tools import generate_openai_tools, execute_tool

app = Flask(__name__)


# 全局变量存储对话历史
conversation_history = [
    {
        "role": "assistant",
        "content": """你是一个严谨的AI数据助手。

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
        你需要与用户进行持续的多轮对话，直到用户明确表示想要结束对话。请以简洁回答问题，中文回答；
        """
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
            'response': '再见！',
            'end_conversation': True
        })

    conversation_history.append({"role": "user", "content": user_message})

    response = chat_completion_request(
        messages=conversation_history,
        tools=generate_openai_tools(),
    )

    message = response.choices[0].message

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

        # 执行所有工具
        for call in message.tool_calls:

            fn_name = call.function.name

            fn_args = json.loads(
                call.function.arguments
            )

            # 执行函数
            print(f"Executing tool: {fn_name} with arguments: {fn_args}")
            tool_result = execute_tool(tool_name=fn_name, arguments=fn_args)

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
    # 模型正常回复
    elif message.content:
        
        content = message.content

        conversation_history.append({
            "role": "assistant",
            "content": content
        })

        return jsonify({
            "response": content,
            "end_conversation": False
        })

if __name__ == "__main__":
    app.run(debug=True)
