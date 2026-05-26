"""工具注册中心（改进版）"""
from typing import Callable, Type, Dict, Any, Optional
from pydantic import BaseModel

from logger import get_logger

logger = get_logger(__name__)

# ============================================================
# 工具注册表
# ============================================================

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {}


def tool(
    params_model: Optional[Type[BaseModel]] = None,
    description: str = "",
    when_to_use: str = "",
    when_not_to_use: str = "",
    examples: Optional[list] = None
):
    """
    工具装饰器，用于注册工具到全局注册表
    
    参数：
        params_model: 参数验证模型（Pydantic BaseModel）
        description: 工具描述
        when_to_use: 何时使用此工具
        when_not_to_use: 何时不使用此工具
        examples: 使用示例列表
    
    返回：
        装饰器函数
    """
    def decorator(func: Callable):
        tool_name = func.__name__
        
        TOOL_REGISTRY[tool_name] = {
            "name": tool_name,
            "description": description or (func.__doc__.strip() if func.__doc__ else ""),
            "when_to_use": when_to_use,
            "when_not_to_use": when_not_to_use,
            "examples": examples or [],
            "schema": params_model.model_json_schema() if params_model else {"type": "object", "properties": {}},
            "params_model": params_model,
            "func": func,
        }
        
        logger.debug(f"Registered tool: {tool_name}")
        return func
    
    return decorator


def generate_openai_tools() -> list:
    """
    生成 OpenAI 兼容的工具 schema
    
    返回：
        工具 schema 列表
    """
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
    
    logger.debug(f"Generated {len(tools)} OpenAI tools")
    return tools


def execute_tool(tool_name: str, arguments: dict) -> dict:
    """
    执行指定的工具
    
    参数：
        tool_name: 工具名称
        arguments: 工具参数（字典）
    
    返回：
        执行结果 {"success": bool, "result": Any} 或 {"success": False, "error": str}
    """
    try:
        # 检查工具是否存在
        if tool_name not in TOOL_REGISTRY:
            raise ValueError(f"工具不存在: {tool_name}")
        
        tool_info = TOOL_REGISTRY[tool_name]
        params_model = tool_info["params_model"]
        func = tool_info["func"]
        
        # 参数验证
        if params_model:
            try:
                validated_params = params_model(**arguments)
                arguments = validated_params.model_dump()
            except Exception as e:
                logger.error(f"Tool parameter validation failed: {e}")
                raise ValueError(f"参数验证失败: {str(e)}")
        
        # 执行工具
        logger.info(f"Executing tool: {tool_name} with args: {arguments}")
        result = func(**arguments)
        
        logger.info(f"Tool {tool_name} executed successfully")
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        logger.exception(f"Tool execution error: {tool_name}")
        return {
            "success": False,
            "error": str(e)
        }


def unregister_tool(tool_name: str) -> bool:
    """
    从注册表中卸载工具
    
    参数：
        tool_name: 工具名称
    
    返回：
        是否成功卸载
    """
    if tool_name in TOOL_REGISTRY:
        del TOOL_REGISTRY[tool_name]
        logger.info(f"Unregistered tool: {tool_name}")
        return True
    return False


def get_tool_info(tool_name: str) -> Optional[Dict[str, Any]]:
    """
    获取工具信息
    
    参数：
        tool_name: 工具名称
    
    返回：
        工具信息字典
    """
    return TOOL_REGISTRY.get(tool_name)


# ============================================================
# 导入并注册内置工具
# ============================================================

try:
    import tools.point_tool  # noqa: F401
    import tools.time_tool  # noqa: F401
    import tools.db_tool  # noqa: F401
except Exception as e:
    logger.warning(f"Failed to import tools: {e}")
