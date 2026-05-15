import os
import json
from typing import Optional, Dict, Any, Callable, Type, List, Literal, Tuple

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from utils.db_table import DATABASE_SCHEMA
from server.llm_server import get_answer

# =========================================================
# Schema Layer
# =========================================================

SCHEMA = DATABASE_SCHEMA

# 保持本模块为数据库适配层：不在此处注册工具到工具中心


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

        if ";" in sql_lower:
            raise ValueError("禁止多语句 SQL")
    
        if " limit " not in f" {sql_lower} ":
            sql += " LIMIT 100"

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
    db_schema: Dict[str, Any]


class QueryTask(BaseModel):
    name: str
    plan: QueryPlan


class QueryTaskList(BaseModel):
    tasks: List[QueryTask]


# =========================================================
# Build Query Plan
# =========================================================
def build_query_tasks(question: str, schema: Dict[str, Any]) -> QueryTaskList:
    """
    将用户问题拆解为多个查询任务
    """

    schema_json = json.dumps(
        schema,
        ensure_ascii=False,
        indent=2
    )

    prompt = f"""
            你是企业级 SQL 查询规划助手。

            你的任务：

            根据：

            1. 用户问题
            2. 数据库 schema

            生成：

            结构化查询任务列表。

            ======================================================

            重要规则：

            1. 只能使用 schema 中存在的表和字段

            2. 禁止虚构字段

            3. 返回必须是 JSON

            4. 不允许 markdown

            5. 不允许解释

            6. aggregation.type 只能是：

            - sum
            - count
            - avg
            - none

            7. filters.op 只能是：

            - eq
            - between
            - last_n_days

            ======================================================

            如果用户问题包含：

            - 多个统计对象
            - 多个实体
            - 多个查询需求

            必须拆分为多个 tasks。

            ======================================================

            返回格式：

            {{
                "tasks": [
                    {{
                        "name": "任务名称",

                        "plan": {{

                            "table": "表名",

                            "select": [
                                "字段"
                            ],

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
                    }}
                ]
            }}

            ======================================================

            数据库 schema:

            {schema_json}

            ======================================================

            用户问题:

            {question}

            ======================================================

            示例：

            用户：
            “请帮我查询老师和学生各有多少人”

            返回：

            {{
            "tasks": [
                {{
                "name": "查询教师人数",

                "plan": {{
                    "table": "teacher",
                    "select": [],
                    "filters": [],
                    "aggregation": {{
                    "type": "count",
                    "field": null
                    }}
                }}
                }},
                {{
                "name": "查询学生人数",

                "plan": {{
                    "table": "student",
                    "select": [],
                    "filters": [],
                    "aggregation": {{
                    "type": "count",
                    "field": null
                    }}
                }}
                }}
            ]
            }}

            ======================================================

            现在开始返回 JSON：
            """

    result = get_answer(prompt)

    print("\n================ RAW TASKS ================\n")
    print(result)

    # =====================================================
    # String -> Dict
    # =====================================================

    if isinstance(result, str):

        result = (
            result
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        try:
            result = json.loads(result)

        except Exception:

            repair_prompt = f"""
                修复以下 JSON:

                {result}

                只返回合法 JSON
                """

            repaired = get_answer(repair_prompt)

            result = json.loads(repaired)

    tasks = QueryTaskList.model_validate(result)

    print("\n================ TASKS ================\n")
    print(tasks.model_dump())

    return tasks

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

    if agg.type in ["sum", "avg"]:

        if not agg.field:
            raise ValueError(
                "sum/avg 必须指定 field"
            )

        if agg.field not in table_fields:
            raise ValueError(
                f"非法 aggregation 字段: {agg.field}"
            )
        
    if agg.type == "none" and not plan.select:
        raise ValueError(
            "非聚合查询 select 不能为空"
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
                f"DATE_SUB(NOW(), "
                f"INTERVAL :{param_key} DAY)"
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
# Run Query Tasks
# =========================================================

def run_query(question: str):

    # =====================================================
    # 1. Build Tasks
    # =====================================================

    tasks = build_query_tasks(
        question=question,
        schema=SCHEMA
    )

    # =====================================================
    # 2. Execute Tasks
    # =====================================================

    results = []

    for task in tasks.tasks:
        try:

            print(
                f"\n================ TASK: {task.name} ================\n"
            )

            plan = task.plan

            # -------------------------------------------------
            # Validate
            # -------------------------------------------------

            validate_plan(plan)

            # -------------------------------------------------
            # Build SQL
            # -------------------------------------------------

            sql, params = build_sql(plan)

            print("\n================ SQL ================\n")
            print(sql)

            print("\n================ PARAMS ================\n")
            print(params)

            # -------------------------------------------------
            # Execute SQL
            # -------------------------------------------------

            query_result = DBService.execute_select(
                sql,
                params
            )

            print("\n================ RESULT ================\n")
            print(query_result)

            # -------------------------------------------------
            # Save Result
            # -------------------------------------------------

            results.append({
                "task_name": task.name,
                "query_plan": plan.model_dump(),
                "sql": sql,
                "params": params,
                "data": query_result
            })
        except Exception as e:
            results.append({
                "task_name": task.name,
                "success": False,
                "error": str(e)
            })

    return {
        "success": True,
        "tasks": results
    }
