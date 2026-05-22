from typing import Dict, Any, Tuple

from models.query_plan import QueryPlan


def build_sql(
    plan: QueryPlan
) -> Tuple[str, Dict[str, Any]]:

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

        # =================================================
        # EQ
        # =================================================

        if f.op == "eq":

            conditions.append(
                f"{f.field} = :{param_key}"
            )

            params[param_key] = f.value

        # =================================================
        # NEQ
        # =================================================

        elif f.op == "neq":

            conditions.append(
                f"{f.field} != :{param_key}"
            )

            params[param_key] = f.value

        # =================================================
        # GT
        # =================================================

        elif f.op == "gt":

            conditions.append(
                f"{f.field} > :{param_key}"
            )

            params[param_key] = f.value

        # =================================================
        # GTE
        # =================================================

        elif f.op == "gte":

            conditions.append(
                f"{f.field} >= :{param_key}"
            )

            params[param_key] = f.value

        # =================================================
        # LT
        # =================================================

        elif f.op == "lt":

            conditions.append(
                f"{f.field} < :{param_key}"
            )

            params[param_key] = f.value

        # =================================================
        # LTE
        # =================================================

        elif f.op == "lte":

            conditions.append(
                f"{f.field} <= :{param_key}"
            )

            params[param_key] = f.value

        # =================================================
        # BETWEEN
        # =================================================

        elif f.op == "between":

            conditions.append(
                f"{f.field} BETWEEN "
                f":{param_key}_start "
                f"AND "
                f":{param_key}_end"
            )

            params[f"{param_key}_start"] = f.value[0]
            params[f"{param_key}_end"] = f.value[1]

        # =================================================
        # IN
        # =================================================

        elif f.op == "in":

            placeholders = []

            for i, v in enumerate(f.value):

                k = f"{param_key}_{i}"

                placeholders.append(f":{k}")

                params[k] = v

            conditions.append(
                f"{f.field} IN ({', '.join(placeholders)})"
            )

        # =================================================
        # LIKE
        # =================================================

        elif f.op == "like":

            conditions.append(
                f"{f.field} LIKE :{param_key}"
            )

            params[param_key] = f"%{f.value}%"

        # =================================================
        # IS NULL
        # =================================================

        elif f.op == "is_null":

            conditions.append(
                f"{f.field} IS NULL"
            )

        # =================================================
        # IS NOT NULL
        # =================================================

        elif f.op == "is_not_null":

            conditions.append(
                f"{f.field} IS NOT NULL"
            )

        # =================================================
        # LAST N DAYS
        # =================================================

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