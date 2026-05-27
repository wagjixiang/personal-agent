'''
Author: Wang Jixiang
Date: 2026-05-26 17:09:36
LastEditors: Wang Jixiang
LastEditTime: 2026-05-26 18:16:11
Description: 
'''
import json

from llm.llm_api import get_answer

from models.query_plan import QueryTaskList

from schema.planner_prompt import (
    build_planner_prompt
)

from schema.schema_manager import (
    get_schema
)

from schema.relation_manager import (
    build_relation_text
)

from sql.validator import validate_plan
from sql.builder import build_sql
from sql.executor import DBExecutor

from utils.json_utils import safe_json_loads


class QueryAgent:

    @classmethod
    def build_query_tasks(
        cls,
        question: str
    ):

        schema = get_schema()

        schema_json = json.dumps(
            schema,
            ensure_ascii=False,
            indent=2
        )

        relation_text = build_relation_text()

        prompt = build_planner_prompt(
            question=question,
            schema_json=schema_json,
            relation_text=relation_text
        )

        result = get_answer(prompt)

        if isinstance(result, str):

            result = safe_json_loads(result)

        return QueryTaskList.model_validate(result)

    @classmethod
    def run(
        cls,
        question: str
    ):

        tasks = cls.build_query_tasks(question)

        results = []

        for task in tasks.tasks:

            try:

                plan = task.plan

                validate_plan(plan)

                sql, params = build_sql(plan)

                data = DBExecutor.execute(
                    sql,
                    params
                )

                results.append({
                    "task_name": task.name,
                    "success": True,
                    "sql": sql,
                    "params": params,
                    "data": data
                })

            except Exception as e:

                results.append({
                    "task_name": task.name,
                    "success": False,
                    "error": str(e)
                })

        return results