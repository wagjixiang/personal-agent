from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

MAX_LIMIT = 1000

FieldOp = Literal[
    "eq",
    "neq",

    "gt",
    "gte",

    "lt",
    "lte",

    "between",

    "in",

    "like",

    "is_null",
    "is_not_null",

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