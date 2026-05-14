import numpy as np
from scipy.spatial.distance import cdist
import json
from typing import Callable, Type, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from datetime import date, datetime

from utils.db_tools import run_query

# =========================================
# Tool Registry
# =========================================

TOOL_REGISTRY = {}

# =========================================
# Tool Decorator
# =========================================

def tool(params_model: Type[BaseModel] | None = None):
    """
    自动注册 tool
    """

    def decorator(func: Callable):
        """
        自动注册 tool
        """

        TOOL_REGISTRY[func.__name__] = {
            "name": func.__name__,
            "description": func.__doc__.strip() if func.__doc__ else "",
            "schema": params_model.model_json_schema() if params_model else {
                "type": "object",
                "properties": {}
            },
            "params_model": params_model,
            "func": func
        }

        return func

    return decorator

# =========================================
# Tool Param Model
# =========================================

# ===================================
# Point Tool
# ===================================

class PointParam(BaseModel):

    target_point: list[float] = Field(
        description="目标点坐标 [x, y]",
        min_length=2,
        max_length=2
    )

    top_k: int = Field(
        default=1,
        description="返回最近点数量"
    )

@tool(PointParam)
def find_point(target_point: PointParam):
    """
    查找距离目标点最近的数据点

    Args:
        target_point (PointParam): 目标点坐标 [x, y]

    Returns:
        dict: 最近点的坐标
    """
    # 读取num_data.json文件
    with open('num_data.json', 'r', encoding='utf-8') as f:
        num_data = json.load(f)

    # 将数据转换为numpy数组
    data_points = np.array(num_data)
    target = np.array([target_point])

    # 计算所有点到目标点的距离
    distances = cdist(data_points, target)

    # 找到最近点的索引
    nearest_idx = np.argmin(distances)
    nearest_point = data_points[nearest_idx]

    return {
        "nearest_point": list(nearest_point)
    }

# ===================================
# Time Tool
# ===================================

# 查询当前时间的工具。返回结果示例："当前时间：2024-04-15 17:15:18。"
@tool()
def get_current_time():
    """
    查询当前时间
    
    Returns:
        dict: {"time": "yyyy-mm-dd hh:mm:ss"}
    """
    # 获取当前日期和时间
    current_datetime = datetime.now()
    # 格式化当前日期和时间
    formatted_time = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
    # 返回格式化后的当前时间
    return {"time": formatted_time}

# =========================================
# SELECT TOOLS
# =========================================

def json_serializer(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


class QueryPlanParam(BaseModel):
    question: str

@tool(QueryPlanParam)
def select_tool(question: QueryPlanParam):
    """
    这是一个数据库查询工具，接受一个需要用到数据库的问题，返回查询结果。

    Args:
        query_plan (QueryPlanParam): 查询计划，包含问题和数据库模式

    Returns:
        dict: 查询结果

    """
    result = run_query(question)

    print("\n============== RESULT ==============\n")

    return json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=json_serializer
        )
    
# =========================================
# 自动生成 OpenAI Tool Schema
# =========================================

def generate_openai_tools():

    tools = []

    for tool_name, tool_info in TOOL_REGISTRY.items():

        tool_schema = {
            "type": "function",
            "function": {
                "name": tool_info["name"],
                "description": tool_info["description"],
                "parameters": tool_info["schema"]
            }
        }

        tools.append(tool_schema)

    return tools

# =========================================
# 模拟 LLM 返回 Tool Call
# =========================================

llm_response = {
    "tool_name": "find_point",
    "arguments": {
        "target_point": [10, 20],
        "top_k": 3
    }
}

# =========================================
# Tool Runtime
# =========================================

def execute_tool(tool_name: str, arguments: dict):

    # 找到 tool
    tool_info = TOOL_REGISTRY[tool_name]

    # 获取参数模型
    params_model = tool_info["params_model"]

    # Pydantic 自动校验参数
    params = params_model(**arguments)

    # 获取函数
    func = tool_info["func"]

    # 执行函数
    result = func(params)

    return result

# =========================================
# 测试
# =========================================

if __name__ == "__main__":

    print("\n================ Tool Schema ================\n")

    tools = generate_openai_tools()

    print(json.dumps(tools, ensure_ascii=False, indent=2))

    print("\n================ Execute Tool ================\n")

    result = execute_tool(
        llm_response["tool_name"],
        llm_response["arguments"]
    )

    print("\n执行结果:")
    print(result)
