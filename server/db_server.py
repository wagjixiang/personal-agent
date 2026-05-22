import os
import json
from typing import Optional, Dict, Any, List, Literal, Tuple, Set

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from utils.db_table import DATABASE_SCHEMA, RELATIONS
from llm.chat_api import get_answer

# =========================================================
# Global Config
# =========================================================

SCHEMA = DATABASE_SCHEMA

MAX_LIMIT = 1000

ALLOWED_AGG_TYPES = {
    "sum",
    "count",
    "avg",
    "none"
}

ALLOWED_FILTER_OPS = {
    "eq",
    "between",
    "last_n_days"
}

ALLOWED_JOIN_TYPES = {
    "inner",
    "left",
    "right"
}


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
            f"?charset=utf8mb4"
        )

        cls._engine = create_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
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

        # =====================================================
        # Security Check
        # =====================================================

        if not sql_lower.startswith("select"):
            raise ValueError("只允许 SELECT 语句")

        if ";" in sql_lower:
            raise ValueError("禁止多语句 SQL")

        forbidden_keywords = [
            "insert",
            "update",
            "delete",
            "drop",
            "alter",
            "truncate",
            "create",
            "replace"
        ]

        for keyword in forbidden_keywords:

            if keyword in sql_lower:
                raise ValueError(f"非法 SQL 关键字: {keyword}")

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

            raise RuntimeError(f"数据库执行失败: {str(e)}")


# =========================================================
# Query Models
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

JoinType = Literal[
    "inner",
    "left",
    "right"
]


class Filter(BaseModel):

    field: str
    op: FieldOp
    value: Any


class Aggregation(BaseModel):

    type: AggType

    field: Optional[str] = None

    distinct: bool = False

    alias: str = "result"


class OrderBy(BaseModel):

    field: str

    direction: Literal["asc", "desc"]


class JoinCondition(BaseModel):

    left_field: str

    right_field: str


class Join(BaseModel):

    table: str

    join_type: JoinType = "inner"

    on: JoinCondition


class QueryPlan(BaseModel):

    main_table: str

    joins: List[Join] = []

    select: List[str] = []

    filters: List[Filter] = []

    aggregation: Aggregation

    group_by: List[str] = []

    order_by: List[OrderBy] = []

    limit: int = Field(default=100, le=MAX_LIMIT)

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, v):

        if v <= 0:
            return 100

        return min(v, MAX_LIMIT)


class QueryTask(BaseModel):

    name: str

    plan: QueryPlan


class QueryTaskList(BaseModel):

    tasks: List[QueryTask]


# =========================================================
# Utils
# =========================================================

def build_relation_text() -> str:

    lines = []

    for r in RELATIONS:

        lines.append(
            f"{r['left_table']}.{r['left_field']} "
            f"= "
            f"{r['right_table']}.{r['right_field']}"
        )

    return "\n".join(lines)


def get_allowed_tables(plan: QueryPlan) -> Set[str]:

    tables = {
        plan.main_table
    }

    for join in plan.joins:
        tables.add(join.table)

    return tables


def get_allowed_fields(plan: QueryPlan) -> Set[str]:

    allowed_tables = get_allowed_tables(plan)

    fields = set()

    for table in allowed_tables:

        if table not in SCHEMA:
            continue

        for field in SCHEMA[table]["fields"]:

            fields.add(
                f"{table}.{field}"
            )

    return fields


def safe_json_loads(raw: str) -> Dict[str, Any]:

    raw = (
        raw
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    try:

        return json.loads(raw)

    except Exception:

        repair_prompt = f"""
你是 JSON 修复助手。

请修复下面的 JSON。

要求：

1. 只返回 JSON
2. 不要 markdown
3. 不要解释
4. 保持原始字段结构

待修复 JSON:

{raw}
"""

        repaired = get_answer(repair_prompt)

        repaired = (
            repaired
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        return json.loads(repaired)


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

    relation_text = build_relation_text()

    prompt = f"""
你是企业级 SQL 查询规划助手。

你的任务：

根据：

1. 用户问题
2. 数据库 schema
3. 表关系

生成结构化查询任务。

======================================================

规则：

1. 只能使用 schema 中存在的表和字段
2. 所有字段必须使用 table.field 格式
3. 禁止虚构字段
4. 返回必须是 JSON
5. 不允许 markdown
6. 不允许解释
7. aggregation.type 只能是:
   - sum
   - count
   - avg
   - none
8. filters.op 只能是:
   - eq
   - between
   - last_n_days
9. join_type 只能是:
   - inner
   - left
   - right

======================================================

聚合规则：

1. aggregation.alias 必须存在
2. order_by 只能使用:
   - alias
   - group_by字段
   - select字段

3. 禁止使用:
   - count(...)
   - sum(...)
   - avg(...)

======================================================

如果用户问题包含多个查询需求，
必须拆分为多个 tasks。

======================================================

数据库关系：

{relation_text}

======================================================

数据库 schema：

{schema_json}

======================================================

用户问题：

{question}

======================================================

返回格式：

{{
    "tasks": [
        {{
            "name": "任务名称",

            "plan": {{

                "main_table": "tb_student",

                "joins": [
                    {{
                        "table": "tb_score",

                        "join_type": "inner",

                        "on": {{
                            "left_field": "tb_student.stu_id",
                            "right_field": "tb_score.stu_id"
                        }}
                    }}
                ],

                "select": [
                    "tb_student.stu_name"
                ],

                "filters": [],

                "aggregation": {{
                    "type": "count",
                    "field": "tb_score.score",
                    "distinct": false,
                    "alias": "result"
                }},

                "group_by": [
                    "tb_student.stu_name"
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

现在开始返回 JSON：
"""

    result = get_answer(prompt)

    print("\n================ RAW TASKS ================\n")
    print(result)

    if isinstance(result, str):

        result = safe_json_loads(result)

    tasks = QueryTaskList.model_validate(result)

    print("\n================ TASKS ================\n")
    print(tasks.model_dump())

    return tasks


# =========================================================
# Validator
# =========================================================

def validate_join_relation(
    left_field: str,
    right_field: str
):

    valid_relations = set()

    for r in RELATIONS:

        a = (
            f"{r['left_table']}.{r['left_field']}",
            f"{r['right_table']}.{r['right_field']}"
        )

        b = (
            f"{r['right_table']}.{r['right_field']}",
            f"{r['left_table']}.{r['left_field']}"
        )

        valid_relations.add(a)
        valid_relations.add(b)

    if (left_field, right_field) not in valid_relations:

        raise ValueError(
            f"非法 JOIN 关系: "
            f"{left_field} = {right_field}"
        )


def validate_plan(plan: QueryPlan):

    # =====================================================
    # Main Table
    # =====================================================

    if plan.main_table not in SCHEMA:

        raise ValueError(
            f"非法主表: {plan.main_table}"
        )

    # =====================================================
    # Join Tables
    # =====================================================

    for join in plan.joins:

        if join.table not in SCHEMA:

            raise ValueError(
                f"非法 JOIN 表: {join.table}"
            )

    # =====================================================
    # Allowed Fields
    # =====================================================

    allowed_fields = get_allowed_fields(plan)

    # =====================================================
    # SELECT
    # =====================================================

    for field in plan.select:

        if field not in allowed_fields:

            raise ValueError(
                f"非法 select 字段: {field}"
            )

    # =====================================================
    # FILTER
    # =====================================================

    for f in plan.filters:

        if f.field not in allowed_fields:

            raise ValueError(
                f"非法 filter 字段: {f.field}"
            )
            
        if f.op == "in":

            if not isinstance(f.value, list):

                raise ValueError(
                    "in 操作 value 必须为 list"
                )

        if f.op == "between":

            if (
                not isinstance(f.value, list)
                or len(f.value) != 2
            ):

                raise ValueError(
                    "between value 必须长度为2"
                )

    # =====================================================
    # GROUP BY
    # =====================================================

    for field in plan.group_by:

        if field not in allowed_fields:

            raise ValueError(
                f"非法 group_by 字段: {field}"
            )

    # =====================================================
    # AGGREGATION
    # =====================================================

    agg = plan.aggregation

    if agg.type not in ALLOWED_AGG_TYPES:

        raise ValueError(
            f"非法 aggregation.type: {agg.type}"
        )

    if agg.field:

        if agg.field not in allowed_fields:

            raise ValueError(
                f"非法 aggregation 字段: {agg.field}"
            )

    # =====================================================
    # ORDER BY
    # =====================================================

    valid_order_fields = set()

    valid_order_fields.update(allowed_fields)
    valid_order_fields.update(plan.select)
    valid_order_fields.update(plan.group_by)

    if agg.alias:
        valid_order_fields.add(agg.alias)

    for o in plan.order_by:

        if o.field not in valid_order_fields:

            raise ValueError(
                f"非法排序字段: {o.field}"
            )

    # =====================================================
    # JOIN RELATION
    # =====================================================

    for join in plan.joins:

        validate_join_relation(
            join.on.left_field,
            join.on.right_field
        )


# =========================================================
# SQL Builder
# =========================================================

def build_sql(plan: QueryPlan) -> Tuple[str, Dict[str, Any]]:

    params = {}

    agg = plan.aggregation

    # =====================================================
    # SELECT
    # =====================================================

    select_fields = []

    # group by 字段自动补入
    for field in plan.group_by:

        if field not in select_fields:
            select_fields.append(field)

    # 非聚合 select
    for field in plan.select:

        if field not in select_fields:
            select_fields.append(field)

    # 聚合
    if agg.type == "sum":

        select_fields.append(
            f"SUM({agg.field}) AS {agg.alias}"
        )

    elif agg.type == "count":

        if agg.distinct and agg.field:

            select_fields.append(
                f"COUNT(DISTINCT {agg.field}) AS {agg.alias}"
            )

        elif agg.field:

            select_fields.append(
                f"COUNT({agg.field}) AS {agg.alias}"
            )

        else:

            select_fields.append(
                f"COUNT(*) AS {agg.alias}"
            )

    elif agg.type == "avg":

        select_fields.append(
            f"AVG({agg.field}) AS {agg.alias}"
        )

    select_clause = ",\n    ".join(select_fields)

    # =====================================================
    # JOIN
    # =====================================================

    join_clauses = []

    for join in plan.joins:

        join_sql = f"""
{join.join_type.upper()} JOIN {join.table}
ON {join.on.left_field} = {join.on.right_field}
"""

        join_clauses.append(join_sql.strip())

    join_clause = "\n".join(join_clauses)

    # =====================================================
    # WHERE
    # =====================================================

    conditions = []

    for idx, f in enumerate(plan.filters):

        param_key = f"p{idx}"

        if f.op == "eq":

            conditions.append(
                f"{f.field} = :{param_key}"
            )

            params[param_key] = f.value

        elif f.op == "between":

            conditions.append(
                f"{f.field} BETWEEN "
                f":{param_key}_start "
                f"AND "
                f":{param_key}_end"
            )

            params[f"{param_key}_start"] = f.value[0]
            params[f"{param_key}_end"] = f.value[1]

        elif f.op == "last_n_days":

            conditions.append(
                f"{f.field} >= "
                f"DATE_SUB(NOW(), "
                f"INTERVAL :{param_key} DAY)"
            )

            params[param_key] = int(f.value)

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

    limit_clause = f"LIMIT {plan.limit}"

    # =====================================================
    # Final SQL
    # =====================================================

    sql = f"""
            SELECT
                {select_clause}

            FROM {plan.main_table}

            {join_clause}

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

    tasks = build_query_tasks(
        question=question,
        schema=SCHEMA
    )

    results = []

    for task in tasks.tasks:

        try:

            print(
                f"\n================ TASK: {task.name} ================\n"
            )

            plan = task.plan

            print(plan)

            # =================================================
            # Validate
            # =================================================

            validate_plan(plan)

            # =================================================
            # Build SQL
            # =================================================

            sql, params = build_sql(plan)

            print("\n================ SQL ================\n")
            print(sql)

            print("\n================ PARAMS ================\n")
            print(params)

            # =================================================
            # Execute SQL
            # =================================================

            query_result = DBService.execute_select(
                sql,
                params
            )

            print("\n================ RESULT ================\n")
            print(query_result)

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
        "统计每门课程的选课人数，并按人数降序排列"
    )

    print("\n================ FINAL RESULT ================\n")

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )