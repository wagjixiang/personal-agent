# 项目架构说明

## 概览

Personal Agent 是一个基于 LLM 的 AI 助手应用，通过 Function Calling 机制集成数据库查询、工具执行等功能，支持企业级的数据分析和问答服务。

## 核心架构

### 分层设计

```
┌─────────────────────────────────────────────┐
│          Web Layer (Flask)                  │
│  ├─ Home Route (/)                          │
│  └─ Chat API (/chat)                        │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│     Chat Controller (chat_controller.py)    │
│  ├─ Request Parsing                         │
│  ├─ Session Management                      │
│  └─ Response Building                       │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│    Agent Executor (agent_executor.py)       │
│  ├─ LLM Loop                                │
│  ├─ Tool Calling                            │
│  └─ Result Aggregation                      │
└──────────────────┬──────────────────────────┘
        ┌──────────┴──────────┐
        │                     │
   ┌────▼──────────┐   ┌─────▼─────────┐
   │  LLM API      │   │ Tool Registry  │
   │ (llm_api.py)  │   │ (tool_registry)│
   └───────────────┘   └────┬──────────┘
                             │
                    ┌────────▼─────────┐
                    │  Custom Tools    │
                    │  ├─ db_tool      │
                    │  ├─ time_tool    │
                    │  └─ point_tool   │
                    └──────────────────┘
```

## 主要模块

### 核心模块（根目录）

| 文件 | 职责 | 说明 |
|------|------|------|
| **app.py** | Flask 应用主入口 | 创建应用，注册路由，启动服务 |
| **chat_controller.py** | 聊天路由控制 | 处理 HTTP 请求，调用 Agent |
| **agent_executor.py** | Agent 循环执行 | 管理 LLM 和 Tool 的交互循环 |
| **conversation_manager.py** | 对话和会话管理 | 维护聊天历史，管理会话存储 |
| **tool_registry.py** | 工具注册中心 | 工具的注册、生成、执行 |
| **llm_api.py** | LLM API 统一接口 | 与 LLM 的通信 |
| **settings.py** | 统一配置管理 | 从 .env 加载和管理所有配置 |
| **constants.py** | 系统常量 | 系统提示词、关键字等常量 |
| **logger.py** | 日志管理 | 统一的日志配置和获取 |
| **json_utils.py** | JSON 工具 | JSON 解析、序列化工具 |
| **exceptions.py** | 统一异常定义 | 应用异常类型定义 |

### agents/ - Agent 模块

| 文件 | 职责 |
|------|------|
| **query_agent.py** | 查询规划Agent，将自然语言转换为 SQL 查询计划 |

### llm/ - LLM 模块

| 文件 | 职责 | 备注 |
|------|------|------|
| **api.py** | LLM API 接口（新） | 统一的 LLM 通信接口 |
| **chat_api.py** | 兼容层 | 保留为了向后兼容 |
| **client.py** | 兼容层 | 保留为了向后兼容 |

### tools/ - 工具模块

| 文件 | 职责 | 用途 |
|------|------|------|
| **db_tool.py** | 数据库查询工具 | 执行数据库查询，返回查询结果 |
| **time_tool.py** | 时间查询工具 | 获取当前时间等时间相关信息 |
| **point_tool.py** | 坐标点工具 | 计算坐标之间的距离 |

### schema/ - 数据库元数据管理

| 文件 | 职责 |
|------|------|
| **schema_manager.py** | 管理数据库表和字段的元数据 |
| **planner_prompt.py** | 为 Planner 生成 prompt |
| **relation_manager.py** | 管理表之间的关系（外键等） |

### sql/ - SQL 处理

| 文件 | 职责 |
|------|------|
| **builder.py** | 将查询计划构建成 SQL 语句 |
| **executor.py** | 执行 SQL，返回结果 |
| **validator.py** | 验证 SQL 的安全性和有效性 |

### server/ - 服务器模块

| 文件 | 职责 |
|------|------|
| **db_server.py** | 数据库连接和执行管理 |

### utils/ - 工具函数

| 文件 | 职责 |
|------|------|
| **db_table.py** | 数据库表的辅助工具 |
| **logger.py** | 兼容层（使用根目录的 logger.py） |
| **json_utils.py** | 兼容层（使用根目录的 json_utils.py） |
| **tools.py** | 兼容层（使用根目录的 tool_registry.py） |

## 数据流

### 聊天流程

```
1. 用户发送消息
   └─> POST /chat { message, session_id }

2. Chat Controller
   ├─ 检查会话 ID（无则生成）
   ├─ 检查对话结束关键词
   └─ 添加用户消息到历史

3. Agent Executor
   ├─ 获取对话历史
   ├─ Loop (最多 MAX_TOOL_ROUNDS 轮):
   │  ├─ 调用 LLM（提供可用工具列表）
   │  ├─ 如果 LLM 回复文本 → 返回答案，结束
   │  └─ 如果 LLM 调用工具:
   │     ├─ 解析工具参数
   │     ├─ 执行工具（Tool Registry）
   │     ├─ 保存工具结果
   │     └─ 继续循环（把结果反馈给 LLM）
   └─ 保存更新后的对话历史

4. 返回结果
   └─> { response, session_id, end_conversation }
```

### 会话管理

```
Session Flow:
┌──────────────────────────────────────┐
│ 用户请求（无 session_id）            │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ 生成新 session_id (UUID)             │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ 获取/创建会话历史（包含系统提示）    │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ 添加用户消息                         │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ 执行 Agent 循环                      │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ 保存更新后的历史（修剪超长历史）    │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ 返回结果和 session_id                │
└──────────────────────────────────────┘
```

## 工具系统

### 工具注册

使用 `@tool` 装饰器注册工具：

```python
from tool_registry import tool
from pydantic import BaseModel

class MyParams(BaseModel):
    param1: str

@tool(
    params_model=MyParams,
    description="工具描述",
    when_to_use="何时使用",
    examples=["示例"]
)
def my_tool(param1: str):
    return {"result": "..."}
```

### 工具执行流程

```
1. LLM 输出工具调用
   └─> { id, function: { name, arguments } }

2. Agent Executor 解析
   ├─ 提取工具名和参数
   └─ 调用 Tool Registry

3. Tool Registry
   ├─ 查找工具
   ├─ 验证参数（Pydantic 模型）
   ├─ 执行工具函数
   └─> 返回结果

4. 保存结果到对话历史
   └─> role: "tool", content: JSON 结果

5. 反馈给 LLM，继续循环
```

## 配置管理

### 配置层级（优先级从高到低）

1. **环境变量** - 系统环境变量
2. **.env 文件** - 项目目录下的 .env 文件
3. **代码默认值** - settings.py 中的默认值

### 配置项

```python
# LLM 配置
OPENAI_API_KEY         # API 密钥
GPT_MODEL             # 模型名称
MODEL_URL             # API 地址

# 数据库配置
DB_HOST               # 主机
DB_PORT               # 端口
DB_NAME               # 数据库名
DB_USER               # 用户名
DB_PASS               # 密码

# Flask 配置
FLASK_HOST            # 监听地址
FLASK_PORT            # 监听端口
FLASK_DEBUG           # 调试模式

# 应用配置
MAX_HISTORY           # 保留的最大历史消息数
MAX_TOOL_ROUNDS       # 最大工具调用轮数
```

## 异常处理

### 异常体系

```
AppException (基类)
├── ConfigException      # 配置异常
├── LLMException        # LLM 调用异常
├── ToolException       # 工具执行异常
├── DatabaseException   # 数据库操作异常
└── ValidationException # 参数验证异常
```

### 错误流处理

- **配置缺失** → ConfigException
- **LLM 请求失败** → LLMException
- **工具执行失败** → ToolException（但不会中断循环，直接返回错误信息）
- **数据库操作失败** → DatabaseException
- **参数验证失败** → ValidationException

## 日志系统

### 日志配置

- **级别**: INFO（可通过代码修改）
- **输出**: 控制台 + 日期分割日志文件
- **格式**: `timestamp [LEVEL] logger_name: message`
- **目录**: `./logs/app.YYYY-MM-DD.log`

### 日志使用

```python
from logger import get_logger

logger = get_logger(__name__)
logger.info("Information message")
logger.error("Error message")
logger.exception("Exception with traceback")
```

## 扩展指南

### 添加新工具

1. 在 `tools/` 目录下创建新文件
2. 使用 `@tool` 装饰器定义工具
3. 工具会自动注册到 Tool Registry

### 添加新的会话存储后端

1. 继承 `SessionStore` 抽象基类
2. 实现 `get`, `save`, `delete`, `exists` 方法
3. 在 `conversation_manager.py` 中使用

### 集成新的 LLM

1. 修改 `settings.py` 中的配置
2. 修改 `llm_api.py` 中的初始化逻辑
3. 只要 LLM 支持 OpenAI 兼容 API 即可

## 性能考虑

### 优化点

- **会话存储**: 内存存储快速但有限制，生产环境建议使用 Redis
- **工具缓存**: 可考虑缓存数据库查询结果
- **LLM 请求**: 考虑请求超时和重试机制
- **日志**: 生产环境可调整日志级别

### 瓶颈

- LLM API 调用延迟（网络和模型性能）
- 数据库查询性能
- Tool Registry 中工具数量过多时的查找性能

## 安全考虑

- **SQL 注入防护**: sql/validator.py 进行参数化查询
- **API 安全**: 建议生产环境使用 HTTPS 和认证
- **配置安全**: 敏感信息（API Key、数据库密码）仅从 .env 或环境变量读取
- **工具调用限制**: MAX_TOOL_ROUNDS 防止无限循环

## 部署建议

### 开发环境

```bash
python app.py
```

### 生产环境

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Docker

```dockerfile
FROM python:3.10
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
ENV FLASK_ENV production
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

## 文件清单

### 核心文件（新增/修改）
- ✅ app.py - Flask 应用主入口
- ✅ agent_executor.py - Agent 循环执行引擎
- ✅ chat_controller.py - 聊天控制器
- ✅ conversation_manager.py - 对话管理
- ✅ tool_registry.py - 工具注册中心
- ✅ llm_api.py - LLM 统一接口
- ✅ settings.py - 配置管理
- ✅ constants.py - 系统常量
- ✅ logger.py - 日志管理
- ✅ json_utils.py - JSON 工具
- ✅ exceptions.py - 异常定义

### 兼容层文件（保留为向后兼容）
- ✅ llm/chat_api.py
- ✅ llm/client.py
- ✅ utils/tools.py
- ✅ utils/json_utils.py
- ✅ utils/logger.py

### 已删除/弃用
- ❌ utils/util.py - 空文件
- ❌ demo.py - 已由 app.py 替代

---

文档生成时间: 2026-05-26
