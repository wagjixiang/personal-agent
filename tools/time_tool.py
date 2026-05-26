"""时间查询工具"""
from datetime import datetime

from tool_registry import tool


@tool(
    description="查询当前时间的工具。",
    when_to_use="当用户询问当前时间或时间相关问题时使用",
    examples=["现在几点了？"],
)
def get_current_time():
    """查询当前时间，返回格式为 yyyy-mm-dd HH:MM:SS"""
    current_datetime = datetime.now()
    formatted_time = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
    return {"time": formatted_time}
