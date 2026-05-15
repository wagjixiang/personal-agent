'''
Author: Wang Jixiang
Date: 2026-05-15 10:47:36
LastEditors: Wang Jixiang
LastEditTime: 2026-05-15 14:51:18
Description: 
'''
import json
from datetime import date, datetime
from pydantic import BaseModel

from utils.tools import tool
from server.db_server import run_query


class QueryPlanParam(BaseModel):
    question: str


def json_serializer(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


@tool(
    params_model=QueryPlanParam,
    description="数据库查询工具。返回真实数据库结果。",
    when_to_use="当用户询问真实业务数据（例如 学院、学生、教师、课程）时使用",
    when_not_to_use="不用于常识、数学或编程问题",
    examples=["老师的职称是什么", "学院排名前三的学院是哪些", "学生数量有多少", "老师数量有多少"],
)
def select_tool(question: str):
    result = run_query(question)

    return json.dumps(result, ensure_ascii=False, indent=2, default=json_serializer)
