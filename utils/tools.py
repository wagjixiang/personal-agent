'''
Author: Wang Jixiang
Date: 2026-05-12 18:28:22
LastEditors: Wang Jixiang
LastEditTime: 2026-05-15 10:57:23
Description: 
'''
from typing import Callable, Type, Dict, Any

from pydantic import BaseModel

# 简化后的工具注册中心：仅负责注册、生成 schema、执行工具

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}


def tool(
    params_model: Type[BaseModel] | None = None,
    description: str = "",
    when_to_use: str = "",
    when_not_to_use: str = "",
    examples: list[str] | None = None
):
    def decorator(func: Callable):
        TOOL_REGISTRY[func.__name__] = {
            "name": func.__name__,
            "description": description or (func.__doc__.strip() if func.__doc__ else ""),
            "when_to_use": when_to_use,
            "when_not_to_use": when_not_to_use,
            "examples": examples or [],
            "schema": params_model.model_json_schema() if params_model else {"type": "object", "properties": {}},
            "params_model": params_model,
            "func": func,
        }

        return func

    return decorator


def generate_openai_tools():
    tools = []

    for tool_name, tool_info in TOOL_REGISTRY.items():

        tool_schema = {
            "type": "function",
            "function": {
                "name": tool_info["name"],
                "description": tool_info["description"],
                "parameters": tool_info["schema"],
            },
        }

        tools.append(tool_schema)

    return tools


def execute_tool(tool_name: str, arguments: dict):
    tool_info = TOOL_REGISTRY[tool_name]

    params_model = tool_info["params_model"]

    func = tool_info["func"]

    # 参数校验
    if params_model:
        validated_params = params_model(**arguments)
        arguments = validated_params.model_dump()

    try:
        result = func(**arguments)

        print(f"Tool Name: {tool_name}, Arguments: {arguments}, Result: {result}")

        return {"success": True, "result": result}

    except Exception as e:
        return {"success": False, "error": str(e)}


# 导入内置工具模块以完成注册（这些模块会在导入时使用本模块的 `tool` 装饰器注册到 TOOL_REGISTRY）
try:
    import tools.point_tool  # noqa: F401
    import tools.time_tool  # noqa: F401
    import tools.select_tool  # noqa: F401
except Exception as e:
    # 打印错误以便调试，但不阻止程序启动
    print(f"Warning: failed to import tools package: {e}")
    
