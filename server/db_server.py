import os
import json
from typing import Optional, Dict, Any, List, Literal, Tuple, Set

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from utils.db_table import DATABASE_SCHEMA, RELATIONS
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

    # 主表
    main_table: str

    # JOIN
    joins: List[Join] = []

    # 查询字段
    select: List[str] = []

    # 条件
    filters: List[Filter] = []

    # 聚合
    aggregation: Aggregation

    # 分组
    group_by: List[str] = []

    # 排序
    order_by: List[OrderBy] = []

    # 限制
    limit: int = Field(default=100, le=MAX_LIMIT)


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


# =========================================================
# Build Query Tasks
# =========================================================

def build_query_tasks(question: str, schema: Dict[str, Any]) -> QueryTaskList:

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

                重要规则：

                1. 只能使用 schema 中存在的表和字段

                2. 禁止虚构字段

                3. 返回必须是 JSON

                4. 不允许 markdown

                5. 不允许解释

                ======================================================

                所有字段必须使用：

                table.field

                格式。

                例如：

                student.name
                teacher.name

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

                join_type 只能是：

                - inner
                - left
                - right

                ======================================================

                数据库关系：

                {relation_text}

                ======================================================

                返回格式：

                {{
                    "tasks": [
                        {{
                            "name": "任务名称",

                            "plan": {{

                                "main_table": "student",

                                "joins": [
                                    {{
                                        "table": "score",

                                        "join_type": "inner",

                                        "on": {{
                                            "left_field": "student.id",
                                            "right_field": "score.student_id"
                                        }}
                                    }}
                                ],

                                "select": [
                                    "student.name",
                                    "teacher.name"
                                ],

                                "filters": [],

                                "aggregation": {{
                                    "type": "none",
                                    "field": null,
                                    "distinct": false
                                }},

                                "group_by": [],

                                "order_by": [],

                                "limit": 100
                            }}
                        }}
                    ]
                }}

                ======================================================

                示例：

                用户：
                “查询学生姓名以及对应老师姓名”

                返回：

                {{
                    "tasks": [
                        {{
                            "name": "查询学生老师信息",

                            "plan": {{

                                "main_table": "student",

                                "joins": [
                                    {{
                                        "table": "score",

                                        "join_type": "inner",

                                        "on": {{
                                            "left_field": "student.id",
                                            "right_field": "score.student_id"
                                        }}
                                    }},
                                    {{
                                        "table": "teacher",

                                        "join_type": "inner",

                                        "on": {{
                                            "left_field": "score.teacher_id",
                                            "right_field": "teacher.id"
                                        }}
                                    }}
                                ],

                                "select": [
                                    "student.name",
                                    "teacher.name"
                                ],

                                "filters": [],

                                "aggregation": {{
                                    "type": "none",
                                    "field": null,
                                    "distinct": false
                                }},

                                "group_by": [],

                                "order_by": [],

                                "limit": 100
                            }}
                        }}
                    ]
                }}

                ======================================================

                数据库 schema:

                {schema_json}

                ======================================================

                用户问题：

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
# Validator
# =========================================================

def validate_join_relation(left_field: str,right_field: str):

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
    # MAIN TABLE
    # =====================================================

    if plan.main_table not in SCHEMA:

        raise ValueError(
            f"非法主表: {plan.main_table}"
        )

    # =====================================================
    # JOIN TABLE
    # =====================================================

    for join in plan.joins:

        if join.table not in SCHEMA:

            raise ValueError(
                f"非法 JOIN 表: {join.table}"
            )

    # =====================================================
    # ALLOWED FIELDS
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

    if agg.field:

        if agg.field not in allowed_fields:

            raise ValueError(
                f"非法 aggregation 字段: {agg.field}"
            )

    # =====================================================
    # ORDER BY
    # =====================================================

    valid_order_fields = set(allowed_fields)

    valid_order_fields.add("result")

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

    if plan.group_by:

        select_fields.extend(plan.group_by)

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

    else:

        select_fields.extend(plan.select)

    select_clause = ", ".join(select_fields)

    # =====================================================
    # JOIN
    # =====================================================

    join_clauses = []

    for join in plan.joins:

        join_sql = f"""
                    {join.join_type.upper()} JOIN {join.table}
                    ON {join.on.left_field}
                    =
                    {join.on.right_field}
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

            print(f"\n================ TASK: {task.name} ================\n")

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
        "查询学生姓名以及对应老师姓名"
    )

    print("\n================ FINAL RESULT ================\n")

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )