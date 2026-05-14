import os
import json
from typing import Optional, Dict, Any, Callable, Type, List, Literal, Tuple

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
from sqlalchemy import create_engine, text
import urllib.parse
import pyodbc
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from utils.db_table import DATABASE_SCHEMA
from server.llm_server import get_answer


# =========================================================
# Tool Registry
# =========================================================

TOOL_REGISTRY = {}


def tool(params_model: Optional[Type[BaseModel]] = None):

    def decorator(func: Callable):

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


# =========================================================
# DB Service
# =========================================================

class DBService:

    _engine: Optional[Engine] = None

    @classmethod
    def engine(cls):

        if cls._engine:
            return cls._engine

        load_dotenv()

        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT", "1433")
        dbname = os.getenv("DB_NAME")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASS")

        url = (
            f"mysql+pymysql://{user}:{password}"
            f"@{host}:{port}/{dbname}"
        )

        cls._engine = create_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False
        )

        return cls._engine

    @classmethod
    def execute_select(
        cls,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:

        sql_lower = sql.lower().strip()

        if not sql_lower.startswith("select"):
            raise ValueError("只允许 SELECT")

        forbidden = [
            "insert",
            "update",
            "delete",
            "drop",
            "alter",
            "truncate",
            "create"
        ]

        for keyword in forbidden:
            if keyword in sql_lower:
                raise ValueError(f"非法 SQL: {keyword}")

        try:

            with cls.engine().connect() as conn:

                result = conn.execute(
                    text(sql),
                    params or {}
                )

                return [
                    dict(row._mapping)
                    for row in result.fetchall()
                ]

        except SQLAlchemyError as e:
            raise RuntimeError(f"数据库执行失败: {e}")


# =========================================================
# Schema Layer
# =========================================================

SCHEMA = DATABASE_SCHEMA


# =========================================================
# Query Plan Models
# =========================================================

FieldOp = Literal[
    "eq",
    "between",
    "last_n_days"
]

AggType = Literal[
    "sum",
    "count",
    "avg",
    "none"
]


class Filter(BaseModel):
    field: str
    op: FieldOp
    value: Any


class Aggregation(BaseModel):
    type: AggType
    field: Optional[str] = None


class QueryPlan(BaseModel):
    table: str
    select: List[str]
    filters: List[Filter] = []
    aggregation: Aggregation


class QueryPlanParam(BaseModel):
    question: str
    schema: Dict[str, Any]


# =========================================================
# Build Query Plan
# =========================================================

@tool(QueryPlanParam)
def build_query_plan(params: QueryPlanParam) -> QueryPlan:
    """
    根据用户问题生成结构化查询计划
    """

    schema_json = json.dumps(
        params.schema,
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""
            你是企业级 SQL 查询规划助手。

            你的任务：
            根据用户问题和数据库 schema，
            生成结构化查询计划。

            重要规则：

            1. 只能使用 schema 中存在的表和字段
            2. 禁止虚构字段
            3. 返回必须是 JSON
            4. 不要返回 markdown
            5. 不要返回解释
            6. aggregation.type 只能是:
            - sum
            - count
            - avg
            - none

            7. filters.op 只能是:
            - eq
            - between
            - last_n_days

            返回格式：

            {{
                "table": "表名",
                "select": ["字段"],
                "filters": [
                    {{
                        "field": "字段名",
                        "op": "操作符",
                        "value": "值"
                    }}
                ],
                "aggregation": {{
                    "type": "聚合类型",
                    "field": "字段名"
                }}
            }}

            数据库 schema:

            {schema_json}

            用户问题:

            {params.question}
    """

    result = get_answer(prompt)

    # 如果 get_answer 返回字符串
    if isinstance(result, str):
        result = json.loads(result)

    return QueryPlan.model_validate(result)


# =========================================================
# Plan Validator
# =========================================================

def validate_plan(plan: QueryPlan):

    # 检查表
    if plan.table not in SCHEMA:
        raise ValueError(f"非法表: {plan.table}")

    table_fields = SCHEMA[plan.table]["fields"]

    # 检查 select 字段
    for field in plan.select:

        if field not in table_fields:
            raise ValueError(f"非法 select 字段: {field}")

    # 检查 filters
    for f in plan.filters:

        if f.field not in table_fields:
            raise ValueError(
                f"非法 filter 字段: {f.field}"
            )

    # 检查 aggregation
    agg = plan.aggregation

    if agg.type != "none":

        if not agg.field:
            raise ValueError("aggregation.field 不能为空")

        if agg.field not in table_fields:
            raise ValueError(
                f"非法 aggregation 字段: {agg.field}"
            )


# =========================================================
# SQL Builder
# =========================================================

def build_sql(
    plan: QueryPlan
) -> Tuple[str, Dict[str, Any]]:

    table = plan.table

    agg = plan.aggregation

    params = {}

    # =====================================================
    # SELECT
    # =====================================================

    if agg.type == "sum":

        select_clause = (
            f"SUM({agg.field}) AS result"
        )

    elif agg.type == "count":

        select_clause = "COUNT(*) AS result"

    elif agg.type == "avg":

        select_clause = (
            f"AVG({agg.field}) AS result"
        )

    else:

        select_clause = ", ".join(plan.select)

    # =====================================================
    # WHERE
    # =====================================================

    conditions = []

    for idx, f in enumerate(plan.filters):

        param_key = f"p{idx}"

        # ---------------------------------------------
        # eq
        # ---------------------------------------------

        if f.op == "eq":

            conditions.append(
                f"{f.field} = :{param_key}"
            )

            params[param_key] = f.value

        # ---------------------------------------------
        # between
        # ---------------------------------------------

        elif f.op == "between":

            conditions.append(
                f"{f.field} BETWEEN "
                f":{param_key}_start "
                f"AND "
                f":{param_key}_end"
            )

            params[f"{param_key}_start"] = f.value[0]
            params[f"{param_key}_end"] = f.value[1]

        # ---------------------------------------------
        # last_n_days
        # ---------------------------------------------

        elif f.op == "last_n_days":

            conditions.append(
                f"{f.field} >= "
                f"DATEADD(day, -:{param_key}, GETDATE())"
            )

            params[param_key] = int(f.value)

    # =====================================================
    # WHERE CLAUSE
    # =====================================================

    where_clause = ""

    if conditions:

        where_clause = (
            "WHERE " + " AND ".join(conditions)
        )

    sql = f"""
SELECT {select_clause}
FROM {table}
{where_clause}
"""

    return sql.strip(), params


# =========================================================
# Query Runner
# =========================================================

def run_query(question: str):

    # =====================================================
    # 1. Build Query Plan
    # =====================================================

    plan = build_query_plan(
        QueryPlanParam(
            question=question,
            schema=SCHEMA
        )
    )

    # =====================================================
    # 2. Validate Plan
    # =====================================================

    validate_plan(plan)

    # =====================================================
    # 3. Build SQL
    # =====================================================

    sql, params = build_sql(plan)

    print("\n================ SQL ================\n")
    print(sql)

    print("\n============== PARAMS ==============\n")
    print(params)

    # =====================================================
    # 4. Execute SQL
    # =====================================================

    result = DBService.execute_select(
        sql,
        params
    )

    return result
