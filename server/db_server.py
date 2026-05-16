import os
import json
from typing import Optional, Dict, Any, List, Literal, Tuple

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from utils.db_table import DATABASE_SCHEMA
from server.llm_server import get_answer

# =========================================================
# Schema Layer
# =========================================================

SCHEMA = DATABASE_SCHEMA

MAX_LIMIT = 1000

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
        port = os.getenv("DB_PORT", "3306")
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
    distinct: bool = False


class OrderBy(BaseModel):
    field: str
    direction: Literal["asc", "desc"]


class QueryPlan(BaseModel):

    table: str

    select: List[str] = []

    filters: List[Filter] = []

    aggregation: Aggregation

    group_by: List[str] = []

    order_by: List[OrderBy] = []

    limit: int = Field(default=100, le=MAX_LIMIT)


class QueryTask(BaseModel):
    name: str
    plan: QueryPlan


class QueryTaskList(BaseModel):
    tasks: List[QueryTask]


# =========================================================
# Build Query Tasks
# =========================================================

def build_query_tasks(
    question: str,
    schema: Dict[str, Any]
) -> QueryTaskList:

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

                生成结构化查询任务。

                ======================================================

                重要规则：

                1. 只能使用 schema 中存在的表和字段

                2. 禁止虚构字段

                3. 返回必须是 JSON

                4. 不允许 markdown

                5. 不允许解释

                ======================================================

                aggregation.type 只能是：

                - sum
                - count
                - avg
                - none

                ======================================================

                filters.op 只能是：

                - eq
                - between
                - last_n_days

                ======================================================

                如果问题包含：

                - 多个统计对象
                - 多个实体
                - 多个查询需求

                必须拆分为多个 tasks。

                ======================================================

                如果问题包含：

                - 每个
                - 每位
                - 各自
                - 分组统计

                必须使用 group_by。

                ======================================================

                如果问题包含：

                - 排序
                - 降序
                - 升序
                - Top N

                必须使用 order_by。

                ======================================================

                如果问题包含：

                - 不同
                - 去重

                必须使用 aggregation.distinct=true

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
                                    "type": "count",
                                    "field": null,
                                    "distinct": false
                                }},

                                "group_by": [
                                    "字段"
                                ],

                                "order_by": [
                                    {{
                                        "field": "字段",
                                        "direction": "desc"
                                    }}
                                ],

                                "limit": 100
                            }}
                        }}
                    ]
                }}

                ======================================================

                示例：

                用户：
                “每位老师的被选课次数并降序排列”

                返回：

                {{
                    "tasks": [
                        {{
                            "name": "统计每位老师被选课次数",

                            "plan": {{
                                "table": "total_school_info",

                                "select": [],

                                "filters": [],

                                "aggregation": {{
                                    "type": "count",
                                    "field": null,
                                    "distinct": false
                                }},

                                "group_by": [
                                    "tea_name"
                                ],

                                "order_by": [
                                    {{
                                        "field": "result",
                                        "direction": "desc"
                                    }}
                                ],

                                "limit": 100
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
修复以下 JSON：

{result}

只返回合法 JSON。
"""

            repaired = get_answer(repair_prompt)

            repaired = (
                repaired
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

            result = json.loads(repaired)

    tasks = QueryTaskList.model_validate(result)

    print("\n================ TASKS ================\n")
    print(tasks.model_dump())

    return tasks


# =========================================================
# Plan Validator
# =========================================================

def validate_plan(plan: QueryPlan):

    # =====================================================
    # Table
    # =====================================================

    if plan.table not in SCHEMA:
        raise ValueError(f"非法表: {plan.table}")

    table_fields = SCHEMA[plan.table]["fields"]

    # =====================================================
    # SELECT
    # =====================================================

    for field in plan.select:

        if field not in table_fields:
            raise ValueError(
                f"非法 select 字段: {field}"
            )

    # =====================================================
    # FILTER
    # =====================================================

    for f in plan.filters:

        if f.field not in table_fields:
            raise ValueError(
                f"非法 filter 字段: {f.field}"
            )

    # =====================================================
    # GROUP BY
    # =====================================================

    for field in plan.group_by:

        if field not in table_fields:
            raise ValueError(
                f"非法 group_by 字段: {field}"
            )

    # =====================================================
    # AGGREGATION
    # =====================================================

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

    # =====================================================
    # ORDER BY
    # =====================================================

    valid_order_fields = set(table_fields)

    valid_order_fields.update(plan.group_by)

    valid_order_fields.add("result")

    for o in plan.order_by:

        if o.field not in valid_order_fields:
            raise ValueError(
                f"非法排序字段: {o.field}"
            )

    # =====================================================
    # NON AGG CHECK
    # =====================================================

    if agg.type == "none":

        if not plan.select:
            raise ValueError(
                "非聚合查询 select 不能为空"
            )

    # =====================================================
    # GROUP BY CHECK
    # =====================================================

    if plan.group_by and agg.type == "none":

        raise ValueError(
            "group_by 必须配合 aggregation"
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

    select_fields = []

    # group by 字段先加入
    if plan.group_by:

        select_fields.extend(plan.group_by)

    # -----------------------------------------------------
    # aggregation
    # -----------------------------------------------------

    if agg.type == "sum":

        select_fields.append(
            f"SUM({agg.field}) AS result"
        )

    elif agg.type == "count":

        if agg.distinct and agg.field:

            select_fields.append(
                f"COUNT(DISTINCT {agg.field}) AS result"
            )

        else:

            select_fields.append(
                "COUNT(*) AS result"
            )

    elif agg.type == "avg":

        select_fields.append(
            f"AVG({agg.field}) AS result"
        )

    # -----------------------------------------------------
    # non aggregation
    # -----------------------------------------------------

    else:

        select_fields.extend(plan.select)

    select_clause = ", ".join(select_fields)

    # =====================================================
    # WHERE
    # =====================================================

    conditions = []

    for idx, f in enumerate(plan.filters):

        param_key = f"p{idx}"

        # -------------------------------------------------
        # eq
        # -------------------------------------------------

        if f.op == "eq":

            conditions.append(
                f"{f.field} = :{param_key}"
            )

            params[param_key] = f.value

        # -------------------------------------------------
        # between
        # -------------------------------------------------

        elif f.op == "between":

            conditions.append(
                f"{f.field} BETWEEN "
                f":{param_key}_start "
                f"AND "
                f":{param_key}_end"
            )

            params[f"{param_key}_start"] = f.value[0]

            params[f"{param_key}_end"] = f.value[1]

        # -------------------------------------------------
        # last_n_days
        # -------------------------------------------------

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

    # =====================================================
    # GROUP BY
    # =====================================================

    group_clause = ""

    if plan.group_by:

        group_clause = (
            "GROUP BY "
            + ", ".join(plan.group_by)
        )

    # =====================================================
    # ORDER BY
    # =====================================================

    order_clause = ""

    if plan.order_by:

        order_items = []

        for o in plan.order_by:

            order_items.append(
                f"{o.field} {o.direction.upper()}"
            )

        order_clause = (
            "ORDER BY "
            + ", ".join(order_items)
        )

    # =====================================================
    # LIMIT
    # =====================================================

    limit_value = min(
        plan.limit,
        MAX_LIMIT
    )

    limit_clause = f"LIMIT {limit_value}"

    # =====================================================
    # FINAL SQL
    # =====================================================

    sql = f"""
SELECT
    {select_clause}
FROM {table}
{where_clause}
{group_clause}
{order_clause}
{limit_clause}
"""

    return sql.strip(), params


# =========================================================
# Run Query
# =========================================================

def run_query(question: str):

    # =====================================================
    # Build Tasks
    # =====================================================

    tasks = build_query_tasks(
        question=question,
        schema=SCHEMA
    )

    # =====================================================
    # Execute Tasks
    # =====================================================

    results = []

    for task in tasks.tasks:

        try:

            print(
                f"\n================ TASK: {task.name} ================\n"
            )

            plan = task.plan

            print(plan)

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
            # Execute
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
                "success": True,
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


# =========================================================
# Example
# =========================================================

if __name__ == "__main__":

    result = run_query(
        "每位老师的被选课次数并降序排列"
    )

    print("\n================ FINAL RESULT ================\n")

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )