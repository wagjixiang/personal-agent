# 项目架构与文件说明 - 优化版

本文档概述仓库中主要目录与文件的职责、内容要点及相互关系，便于快速上手与维护。

> 📢 **重要通知**：项目已进行完整的代码优化和重构。
> - 查看详细迁移说明：[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
> - 查看新的架构文档：[PROJECT_ARCHITECTURE_NEW.md](PROJECT_ARCHITECTURE_NEW.md)

**优化后的项目结构**

```
app.py                         # Flask 应用主入口（替代 demo.py）
agent_executor.py              # Agent 循环执行引擎
chat_controller.py             # 聊天控制器（路由处理）
conversation_manager.py        # 对话和会话管理
tool_registry.py               # 工具注册中心（迁自 utils/tools.py）
llm_api.py                     # LLM API 统一接口（合并 client + chat_api）
settings.py                    # 统一配置管理（替代 config/config.py）
constants.py                   # 系统常量
logger.py                      # 日志管理（迁自 utils/logger.py）
json_utils.py                  # JSON 处理工具（迁自 utils/json_utils.py）
exceptions.py                  # 统一异常定义

agents/
    query_agent.py             # 查询规划 Agent
config/
    config.py                  # 旧配置（已被 settings.py 替代，保留兼容）
llm/
    api.py                     # LLM API 接口（新）
    chat_api.py                # 兼容层
    client.py                  # 兼容层
logs/
    app.YYYY-MM-DD.log         # 日志文件（按日期分割）
models/
    query_plan.py
schema/
    planner_prompt.py
    relation_manager.py
    schema_manager.py
server/
    db_server.py
sql/
    builder.py
    executor.py
    validator.py
templates/
    index.html
tools/
    db_tool.py                 # 数据库查询工具
    point_tool.py              # 坐标计算工具
    time_tool.py               # 时间查询工具
utils/
    db_table.py
    json_utils.py              # 兼容层
    logger.py                  # 兼容层
    tools.py                   # 兼容层
```

**使用说明**

- **快速开始**：查看 [README.md](README.md)
- **迁移指南**：从 demo.py 迁移到 app.py 请见 [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- **详细架构**：查看 [PROJECT_ARCHITECTURE_NEW.md](PROJECT_ARCHITECTURE_NEW.md)

**核心模块说明**

**根目录主要文件**
- **app.py** ✨ (新): Flask 应用主入口，替代旧的 demo.py。清晰简洁（40行），仅处理应用初始化
- **agent_executor.py** ✨ (新): Agent 循环执行引擎，处理 LLM 和工具的交互
- **chat_controller.py** ✨ (新): 聊天路由控制器，处理 HTTP 请求和响应
- **conversation_manager.py** ✨ (新): 对话和会话管理，支持多种存储后端
- **tool_registry.py** ✨ (新): 工具注册中心，统一的工具管理
- **llm_api.py** ✨ (新): LLM API 统一接口，合并原 client.py 和 chat_api.py
- **settings.py** ✨ (新): 统一配置管理，从 .env 加载所有配置
- **constants.py** ✨ (新): 系统常量定义（系统提示、关键字等）
- **logger.py** ✨ (新): 改进的日志管理，迁自 utils/logger.py
- **json_utils.py** ✨ (新): JSON 处理工具，迁自 utils/json_utils.py
- **exceptions.py** ✨ (新): 统一异常定义，支持异常分类处理

**agents/**
- **query_agent.py**: 查询规划 Agent，将用户问题转换为数据库查询计划

**config/**
- **config.py** (已弃用): 配置已迁移到 settings.py，此文件保留兼容性

**llm/** (已优化)
- **api.py** ✨: 新增 LLM API 统一接口
- **chat_api.py**: 兼容层（转发到 llm_api）
- **client.py**: 兼容层（转发到 llm_api）

**logs/**
- 日志文件目录（自动生成，按日期分割）

**models/**
- **query_plan.py**: 查询计划数据结构定义

**schema/**
- **planner_prompt.py**: 规划器提示词模板
- **relation_manager.py**: 表关系管理
- **schema_manager.py**: 数据库元数据管理

**server/**
- **db_server.py**: 数据库连接和执行管理

**sql/**
- **builder.py**: SQL 构建器
- **executor.py**: SQL 执行器
- **validator.py**: SQL 验证器

**templates/**
- **index.html**: 聊天界面前端

**tools/**
- **db_tool.py**: 数据库查询工具（已更新导入）
- **point_tool.py**: 坐标计算工具（已更新导入）
- **time_tool.py**: 时间查询工具（已更新导入）

**utils/** (已优化为兼容层)
- **db_table.py**: 数据库表操作工具
- **json_utils.py**: 兼容层，转发到根目录 json_utils.py
- **logger.py**: 兼容层，转发到根目录 logger.py
- **tools.py**: 兼容层，转发到 tool_registry.py

**快速导航**
- 启动应用: [app.py](app.py) ✨ (新)
- LLM 交互: [llm_api.py](llm_api.py) ✨ (新)
- 工具管理: [tool_registry.py](tool_registry.py) ✨ (新)
- 对话管理: [conversation_manager.py](conversation_manager.py) ✨ (新)
- 数据库操作: [sql/executor.py](sql/executor.py) 与 [server/db_server.py](server/db_server.py)

**主要改进点**
✅ 代码简化: 从 500+ 行混杂代码拆分为清晰的模块  
✅ 职责分离: 每个模块只负责单一职责  
✅ 配置集中: 所有配置通过 settings.py 管理  
✅ 异常统一: 定义了异常体系，便于错误处理  
✅ 日志改进: 统一的日志格式和配置  
✅ 可扩展性: 支持自定义会话存储、异常处理等  
✅ 向后兼容: 通过兼容层保持与旧代码的兼容性  

---
文档更新时间：2026-05-26  
优化版本：2.0

