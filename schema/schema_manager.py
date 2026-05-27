"""
Schema 管理模块

作用：
1. 提供 Schema Retrieval 接口
2. 提供 Prompt 构建接口
3. 提供向后兼容接口
4. 提供缓存统计
"""

from utils.db_table import DATABASE_SCHEMA

from schema.schema_registry import (
    get_registry,
    retrieve_schema,
    build_schema_prompt
)

SCHEMA = DATABASE_SCHEMA


# =========================================================
# 向后兼容
# =========================================================

def get_schema():
    """
    获取完整 Schema

    （向后兼容）
    """

    return SCHEMA


# =========================================================
# 新 Retrieval 接口
# =========================================================

def get_optimized_schema(
    user_query: str
):
    """
    获取优化后的 Schema Retrieval 结果

    返回：
    {
        "tables": [...],
        "selected_columns": {...}
    }
    """

    return retrieve_schema(user_query)


# =========================================================
# Prompt 接口（推荐使用）
# =========================================================

def get_schema_prompt(
    user_query: str
) -> str:
    """
    获取 LLM 专用 Schema Prompt

    推荐：
    QueryPlanner 直接使用这个 Prompt
    """

    return build_schema_prompt(user_query)


# =========================================================
# Cache Stats
# =========================================================

def get_schema_cache_stats():
    """
    获取缓存统计信息
    """

    registry = get_registry()

    return registry.cache.get_cache_stats()


# =========================================================
# Cache Clear
# =========================================================

def clear_schema_cache():
    """
    清空 Schema Retrieval 缓存
    """

    registry = get_registry()

    registry.cache.clear_cache()


# =========================================================
# Debug
# =========================================================

if __name__ == "__main__":

    question = "统计每个学院的学生数量"

    print("=" * 50)
    print("Optimized Schema")
    print("=" * 50)

    result = get_optimized_schema(question)

    print(result)

    print("\n")
    print("=" * 50)
    print("Schema Prompt")
    print("=" * 50)

    prompt = get_schema_prompt(question)

    print(prompt)

    print("\n")
    print("=" * 50)
    print("Cache Stats")
    print("=" * 50)

    print(get_schema_cache_stats())