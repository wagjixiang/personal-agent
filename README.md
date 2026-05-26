# personal-agent

一个本地私有化大模型AI助手应用，通过LLM API和自定义工具实现function calling功能，支持企业级数据查询分析。

## 核心特性

- 🤖 **LLM驱动**: 集成大型语言模型（支持通义千问、GPT等）
- 🛠️ **工具系统**: 灵活的工具注册和执行框架
- 💾 **数据库集成**: 支持MySQL数据查询和分析
- 📝 **对话管理**: 完整的会话管理和历史维护
- 🔄 **Agent循环**: 自动化的Tool Calling和结果处理

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/wagjixiang/personal-agent.git
cd personal-agent
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并填入你的配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```python
# LLM 配置
OPENAI_API_KEY=sk-xxxx          # 替换为你的API Key
GPT_MODEL=qwen-plus              # 模型名称
MODEL_URL=https://...            # 模型API地址

# 数据库配置
DB_HOST=127.0.0.1
DB_NAME=school                   # 你的数据库名
DB_USER=root
DB_PASS=123456
DB_PORT=3306

# Flask 配置
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
FLASK_DEBUG=True
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 运行应用

```bash
# 方式 1: 直接运行
python app.py

# 方式 2: 使用Flask命令
flask run

# 方式 3: 生产环境
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

应用会在 `http://0.0.0.0:5000` 启动

## 项目结构

```
personal-agent/
├── app.py                      # Flask 应用主入口
├── agent_executor.py           # Agent 循环执行引擎
├── chat_controller.py          # 聊天API控制器
├── conversation_manager.py     # 对话和会话管理
├── tool_registry.py            # 工具注册中心
├── llm_api.py                  # LLM API 统一接口
├── settings.py                 # 配置管理
├── constants.py                # 系统常量
├── logger.py                   # 日志管理
├── json_utils.py               # JSON 处理工具
├── exceptions.py               # 统一异常定义
│
├── agents/                     # Agent 模块
│   └── query_agent.py          # 查询规划Agent
├── llm/                        # LLM 模块
│   ├── api.py                  # LLM API接口
│   ├── chat_api.py             # 兼容层
│   └── client.py               # 兼容层
├── tools/                      # 工具定义
│   ├── db_tool.py              # 数据库查询工具
│   ├── time_tool.py            # 时间查询工具
│   └── point_tool.py           # 坐标计算工具
├── schema/                     # 数据库元数据管理
│   ├── schema_manager.py
│   ├── planner_prompt.py
│   └── relation_manager.py
├── sql/                        # SQL 处理
│   ├── builder.py
│   ├── executor.py
│   └── validator.py
├── server/                     # 服务器
│   └── db_server.py
├── utils/                      # 工具函数
│   ├── db_table.py
│   └── ... (其他)
├── models/                     # 数据模型
├── templates/                  # 前端模板
├── logs/                       # 日志目录
├── requirements.txt            # 依赖清单
├── .env.example               # 环境变量示例
└── README.md
```

## API 文档

### 聊天接口

**POST** `/chat`

请求：
```json
{
    "message": "你好",
    "session_id": "optional-uuid"
}
```

响应：
```json
{
    "response": "你好！有什么我可以帮助你的吗？",
    "session_id": "uuid",
    "end_conversation": false
}
```

### 查询对话历史

**GET** `/chat/history/{session_id}`

响应：
```json
{
    "session_id": "uuid",
    "history": [...]
}
```

### 清除会话

**DELETE** `/chat/clear/{session_id}`

## 工具开发

### 注册新工具

在 `tools/` 目录下创建新工具文件，使用 `@tool` 装饰器：

```python
from pydantic import BaseModel
from tool_registry import tool

class MyToolParam(BaseModel):
    param1: str
    param2: int

@tool(
    params_model=MyToolParam,
    description="工具描述",
    when_to_use="何时使用",
    examples=["示例用法"]
)
def my_tool(param1: str, param2: int):
    """工具实现"""
    return {"result": "..."}
```

工具会自动注册到工具注册中心。

## 系统设计

### Agent 循环流程

1. **接收用户消息**: `/chat` 接收用户输入
2. **保存历史**: 消息添加到对话历史
3. **调用LLM**: 使用可用工具列表调用LLM
4. **处理响应**:
   - 如果LLM直接回复，返回答案
   - 如果LLM发起工具调用，执行工具
5. **工具执行**: 执行LLM指定的工具，获取结果
6. **反馈LLM**: 将工具结果返回给LLM
7. **重复循环**: 直到LLM生成最终答案或达到轮数限制
8. **返回结果**: 返回最终答案给用户

### 对话管理

- **会话存储**: 支持多种后端（内存、Redis、数据库）
- **历史维护**: 自动修剪历史，保持在 `MAX_HISTORY` 范围内
- **系统提示**: 通过系统角色消息指导LLM行为

### 配置管理

所有配置统一通过 `settings.py` 管理，支持：
- 环境变量覆盖
- .env 文件配置
- 代码默认值

## 常见问题

### Q: 如何使用其他LLM？
A: 修改 `.env` 中的 `GPT_MODEL` 和 `MODEL_URL`，只要模型支持OpenAI兼容API即可。

### Q: 如何添加新的数据库？
A: 修改 `settings.py` 中的数据库连接配置，或在 `schema/` 中定义新的表元数据。

### Q: 如何扩展工具功能？
A: 在 `tools/` 目录下创建新工具，使用 `@tool` 装饰器注册。

## 已知限制

- 当前使用内存会话存储（建议生产环境使用 Redis）
- 仅支持MySQL数据库（可扩展支持其他数据库）

## 文档和资源

- [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) - 详细架构说明
- [.env.example](.env.example) - 配置模板

## 许可证

MIT License

## 维护者

- Wang Jixiang ([@wagjixiang](https://github.com/wagjixiang))

