"""坐标点距离计算工具"""
from typing import List
import json

import numpy as np
from scipy.spatial.distance import cdist
from pydantic import BaseModel, Field

from tool_registry import tool


class PointParam(BaseModel):
    target_point: List[float] = Field(
        description="目标点坐标 [x, y]",
        min_length=2,
        max_length=2,
    )

    top_k: int = Field(
        default=1,
        description="返回最近点的数量",
    )


@tool(
    params_model=PointParam,
    description="查找距离目标点最近的数据点",
    when_to_use="当用户询问：两点之间的距离、最近的点时使用",
    examples=["和点 [3.5, 4.2] 相聚最近的点是什么？"],
)
def find_point(target_point: list[float], top_k: int = 1):
    """查找距离目标点最近的数据点"""

    with open('num_data.json', 'r', encoding='utf-8') as f:
        num_data = json.load(f)

    data_points = np.array(num_data)

    target = np.array([target_point])

    distances = cdist(data_points, target).flatten()

    # 取 top_k 最小索引
    k = max(1, int(top_k))
    idx = np.argpartition(distances, range(min(k, len(distances))))[:k]

    nearest = [list(map(float, data_points[i].tolist())) for i in idx]

    return {"nearest_points": nearest}
