from typing import Set

from models.query_plan import QueryPlan
from schema.schema_manager import get_schema
from schema.relation_manager import get_relations

SCHEMA = get_schema()


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


def validate_join_relation(
    left_field: str,
    right_field: str
):

    valid_relations = set()

    for r in get_relations():

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

    if plan.main_table not in SCHEMA:

        raise ValueError(
            f"非法主表: {plan.main_table}"
        )

    allowed_fields = get_allowed_fields(plan)

    for field in plan.select:

        if field not in allowed_fields:

            raise ValueError(
                f"非法 select 字段: {field}"
            )

    for join in plan.joins:

        validate_join_relation(
            join.on.left_field,
            join.on.right_field
        )