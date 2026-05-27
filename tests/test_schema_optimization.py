"""
Schema Registry 优化效果测试

测试项目：
1. 缓存功能
2. 改进的相似度算法
3. Token节省效果
4. 表推断准确度
"""

import time
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema.schema_registry import (
    get_registry, 
    infer_tables, 
    get_schema_for_llm,
    get_cache_stats,
    clear_cache
)


def test_cache_performance():
    """测试缓存性能改进"""
    print("\n" + "="*60)
    print("测试1：缓存性能测试")
    print("="*60)
    
    clear_cache()
    registry = get_registry()
    
    query = "查询学生信息和所属学院"
    
    # 第一次查询（缓存未命中）
    start = time.time()
    result1 = registry.infer_tables_from_query(query)
    time1 = time.time() - start
    
    # 第二次查询（缓存命中）
    start = time.time()
    result2 = registry.infer_tables_from_query(query)
    time2 = time.time() - start
    
    print(f"查询: {query}")
    print(f"推断表: {result1}")
    print(f"第一次执行时间: {time1*1000:.3f}ms")
    print(f"第二次执行时间: {time2*1000:.3f}ms")
    print(f"性能提升: {time1/time2:.1f}倍")
    print(f"缓存统计: {get_cache_stats()}")


def test_token_reduction():
    """测试Token节省效果"""
    print("\n" + "="*60)
    print("测试2：Token节省效果")
    print("="*60)
    
    clear_cache()
    
    queries = [
        "查询学生成绩",
        "查询学院排名",
        "查询教师职称",
    ]
    
    total_compact = 0
    total_full = 0
    
    for query in queries:
        # 紧凑格式
        compact_prompt = get_schema_for_llm(query, compact=True)
        tokens_compact = len(compact_prompt) // 4  # 粗略估计，实际应用需tokenizer
        
        # 完整格式
        full_prompt = get_schema_for_llm(query, compact=False)
        tokens_full = len(full_prompt) // 4
        
        total_compact += tokens_compact
        total_full += tokens_full
        
        reduction = ((tokens_full - tokens_compact) / tokens_full) * 100
        
        print(f"\n查询: {query}")
        print(f"  完整格式大小: {len(full_prompt)} 字符 (~{tokens_full} tokens)")
        print(f"  紧凑格式大小: {len(compact_prompt)} 字符 (~{tokens_compact} tokens)")
        print(f"  Token节省: {reduction:.1f}%")
        print(f"  紧凑格式内容:")
        for line in compact_prompt.split('\n')[:5]:
            print(f"    {line}")
    
    print(f"\n总体Token节省: {((total_full - total_compact) / total_full) * 100:.1f}%")


def test_similarity_algorithm():
    """测试改进的相似度算法"""
    print("\n" + "="*60)
    print("测试3：改进的相似度算法测试")
    print("="*60)
    
    clear_cache()
    
    test_queries = [
        ("学生信息", ["tb_student", "tb_college"]),
        ("成绩查询", ["tb_record", "tb_student", "tb_course"]),
        ("教师职位", ["tb_teacher", "tb_college"]),
        ("课程学分", ["tb_course", "tb_teacher"]),
    ]
    
    for query, expected_tables in test_queries:
        result = infer_tables(query)
        matched = all(table in result for table in expected_tables)
        status = "✓" if matched else "✗"
        
        print(f"\n{status} 查询: {query}")
        print(f"  期望表: {expected_tables}")
        print(f"  推断表: {result}")


def test_concurrent_queries():
    """测试多个查询的缓存效率"""
    print("\n" + "="*60)
    print("测试4：并发查询缓存效率")
    print("="*60)
    
    clear_cache()
    
    queries = [
        "查询学生信息",
        "查询成绩",
        "查询学生信息",  # 重复
        "查询成绩",      # 重复
        "查询教师",
        "查询学生信息",  # 重复
    ]
    
    print(f"\n执行 {len(queries)} 次查询...")
    
    start = time.time()
    for query in queries:
        infer_tables(query)
    total_time = time.time() - start
    
    stats = get_cache_stats()
    print(f"\n总执行时间: {total_time*1000:.2f}ms")
    print(f"缓存统计:")
    print(f"  缓存命中: {stats['hits']}")
    print(f"  缓存未命中: {stats['misses']}")
    print(f"  命中率: {stats['hit_rate_percent']:.1f}%")
    print(f"  缓存大小: {stats['cache']['size']} / {stats['cache']['max_size']}")


def test_schema_accuracy():
    """测试Schema推断的准确度"""
    print("\n" + "="*60)
    print("测试5：Schema推断准确度")
    print("="*60)
    
    clear_cache()
    
    test_cases = [
        {
            "query": "查询所有学生的名字",
            "expected_primary": "tb_student",
            "description": "学生表应该是主表"
        },
        {
            "query": "查询学生选了哪些课程",
            "expected_tables": ["tb_student", "tb_record", "tb_course"],
            "description": "应该包含学生、选课记录和课程表"
        },
        {
            "query": "查询某个学院的教师",
            "expected_tables": ["tb_teacher", "tb_college"],
            "description": "应该包含教师表和学院表"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        result = infer_tables(test["query"])
        
        if "expected_primary" in test:
            primary_ok = result and result[0] == test["expected_primary"]
            status = "✓" if primary_ok else "✗"
            print(f"\n{status} 测试用例 {i}: {test['description']}")
            print(f"  查询: {test['query']}")
            print(f"  预期主表: {test['expected_primary']}")
            print(f"  推断结果: {result}")
        else:
            all_matched = all(t in result for t in test["expected_tables"])
            status = "✓" if all_matched else "✗"
            print(f"\n{status} 测试用例 {i}: {test['description']}")
            print(f"  查询: {test['query']}")
            print(f"  预期表: {test['expected_tables']}")
            print(f"  推断结果: {result}")


if __name__ == "__main__":
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║     Schema Registry 优化效果验证测试                       ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    try:
        test_cache_performance()
        test_token_reduction()
        test_similarity_algorithm()
        test_concurrent_queries()
        test_schema_accuracy()
        
        print("\n" + "="*60)
        print("所有测试完成！")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
