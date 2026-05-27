"""
混合智能查询引擎 (Hybrid Query Engine)

功能：
- 语义查询规划（NLU）
- SQL 生成与验证
- 查询缓存与去重
- 自动重试与降级
- 查询性能监控
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from sql.executor import DBExecutor
from sql.builder import build_sql
from sql.validator import SQLValidator
from infra.cache import CacheManager, CacheKeyBuilder
from models.query_plan import QueryPlan

logger = logging.getLogger(__name__)

# ============================================================
# 数据类定义
# ============================================================

@dataclass
class QueryMetrics:
    """查询性能指标"""
    question: str
    semantic_planning_ms: float
    sql_generation_ms: float
    cache_lookup_ms: float
    query_execution_ms: float
    total_ms: float
    cache_hit: bool
    rows_returned: int
    success: bool


class HybridQueryEngine:
    """混合智能查询引擎"""
    
    def __init__(self, cache_manager: CacheManager, validator: SQLValidator):
        self.cache = cache_manager
        self.validator = validator
        self.metrics_history: List[QueryMetrics] = []
    
    def query(
        self,
        question: str,
        use_cache: bool = True,
        max_retries: int = 2
    ) -> Tuple[List[Dict[str, Any]], QueryMetrics]:
        """
        执行混合查询
        
        流程：
        1. 检查缓存中是否有相同问题的查询计划
        2. 如果缓存不存在，使用语义规划器生成 QueryPlan
        3. 生成 SQL
        4. 再次检查查询结果缓存
        5. 如果缓存不存在，执行 SQL
        6. 缓存结果并返回
        
        参数：
            question: 用户问题
            use_cache: 是否使用缓存
            max_retries: 失败重试次数
        
        返回：
            (查询结果, 性能指标)
        """
        import time
        
        start_time = time.time()
        metrics = QueryMetrics(
            question=question,
            semantic_planning_ms=0,
            sql_generation_ms=0,
            cache_lookup_ms=0,
            query_execution_ms=0,
            total_ms=0,
            cache_hit=False,
            rows_returned=0,
            success=False
        )
        
        try:
            # ===== 步骤 1: 检查查询计划缓存 =====
            query_plan = None
            
            if use_cache:
                cache_start = time.time()
                query_plan = self.cache.get_cached_query_plan(question)
                metrics.cache_lookup_ms = (time.time() - cache_start) * 1000
                
                if query_plan:
                    logger.info(f"查询计划缓存命中: {question}")
            
            # ===== 步骤 2: 生成查询计划（如果缓存不存在）=====
            if not query_plan:
                plan_start = time.time()
                query_plan = self._generate_query_plan(question)
                metrics.semantic_planning_ms = (time.time() - plan_start) * 1000
                
                # 缓存查询计划
                if use_cache:
                    self.cache.cache_query_plan(question, query_plan)
            
            # ===== 步骤 3: SQL 生成 =====
            gen_start = time.time()
            sql, params = self._generate_sql(query_plan)
            metrics.sql_generation_ms = (time.time() - gen_start) * 1000
            
            # ===== 步骤 4: 检查查询结果缓存 =====
            results = None
            
            if use_cache:
                results = self.cache.get_cached_query_result(sql, params)
                if results:
                    metrics.cache_hit = True
                    logger.info(f"查询结果缓存命中: {sql[:50]}...")
            
            # ===== 步骤 5: 执行查询（如果缓存不存在）=====
            if results is None:
                exec_start = time.time()
                
                # 首先获取执行计划
                explain_result = DBExecutor.execute(
                    f"EXPLAIN {sql}",
                    params,
                    explain=True
                )
                
                if self._should_optimize_query(explain_result):
                    logger.warning(f"查询可能低效，建议优化: {explain_result}")
                
                # 执行查询（带重试）
                results = self._execute_with_retry(sql, params, max_retries)
                
                metrics.query_execution_ms = (time.time() - exec_start) * 1000
                
                # 缓存结果
                if use_cache and results:
                    self.cache.cache_query_result(sql, results, params, ttl=3600)
            
            metrics.rows_returned = len(results) if results else 0
            metrics.success = True
            
            # 记录指标
            metrics.total_ms = (time.time() - start_time) * 1000
            self.metrics_history.append(metrics)
            
            logger.info(f"查询成功: {metrics.rows_returned} 行, 耗时 {metrics.total_ms:.2f}ms")
            
            return results or [], metrics
        
        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            metrics.total_ms = (time.time() - start_time) * 1000
            self.metrics_history.append(metrics)
            raise
    
    def _generate_query_plan(self, question: str) -> Dict[str, Any]:
        """使用 LLM 生成查询计划"""
        # 这里应该调用 QueryAgent.run(question)
        # 为了演示，返回示例计划
        from agents.query_agent import QueryAgent
        
        logger.info(f"生成查询计划: {question}")
        
        # 从 QueryAgent 获取结果（返回 Dict 或 List）
        result = QueryAgent.run(question)
        
        # 如果返回的是列表（查询结果），转换为查询计划
        if isinstance(result, list):
            return {
                "select": ["*"],
                "from": "results",
                "filters": [],
                "joins": [],
                "group_by": [],
                "aggregation": {"type": "none"},
                "raw_result": result
            }
        
        # 否则假设已经是查询计划格式
        return result
    
    def _generate_sql(self, query_plan: Dict[str, Any]) -> Tuple[str, Dict]:
        """将查询计划转换为 SQL"""
        from models.query_plan import QueryPlan
        from sql.builder import build_sql
        
        # 将字典转换为 QueryPlan 对象
        plan_obj = QueryPlan(**query_plan)
        sql, params = build_sql(plan_obj)
        
        logger.debug(f"生成 SQL: {sql}")
        return sql, params
    
    def _should_optimize_query(self, explain_result: List[Dict]) -> bool:
        """判断查询是否需要优化"""
        if not explain_result:
            return False
        
        for row in explain_result:
            # 如果有 Full table scan，则需要优化
            if row.get('type') == 'ALL':
                return True
            # 如果 rows 数量很大，则需要优化
            if row.get('rows', 0) > 1000000:
                return True
        
        return False
    
    def _execute_with_retry(
        self,
        sql: str,
        params: Dict,
        max_retries: int
    ) -> List[Dict[str, Any]]:
        """带重试机制的查询执行"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"执行查询 (尝试 {attempt + 1}/{max_retries})")
                results = DBExecutor.execute(sql, params)
                return results
            except Exception as e:
                last_error = e
                logger.warning(f"查询执行失败 (尝试 {attempt + 1}): {e}")
                
                if attempt < max_retries - 1:
                    # 指数退避重试
                    import time
                    wait_time = 0.1 * (2 ** attempt)
                    logger.info(f"等待 {wait_time}s 后重试...")
                    time.sleep(wait_time)
        
        if last_error:
            raise last_error
        
        return []
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """获取性能指标摘要"""
        if not self.metrics_history:
            return {}
        
        total_queries = len(self.metrics_history)
        successful = sum(1 for m in self.metrics_history if m.success)
        cache_hits = sum(1 for m in self.metrics_history if m.cache_hit)
        
        avg_total_ms = sum(m.total_ms for m in self.metrics_history) / total_queries
        avg_query_ms = sum(m.query_execution_ms for m in self.metrics_history) / total_queries
        
        return {
            'total_queries': total_queries,
            'successful': successful,
            'failed': total_queries - successful,
            'cache_hit_rate': f"{(cache_hits / total_queries * 100):.1f}%",
            'avg_total_ms': f"{avg_total_ms:.2f}",
            'avg_query_execution_ms': f"{avg_query_ms:.2f}",
        }
    
    def get_slow_queries(self, threshold_ms: float = 1000.0) -> List[QueryMetrics]:
        """获取超过阈值的慢查询"""
        return [m for m in self.metrics_history if m.total_ms > threshold_ms]
    
    def reset_metrics(self):
        """重置性能指标"""
        self.metrics_history.clear()


# ============================================================
# 查询验证器
# ============================================================

class QueryValidator:
    """查询验证与安全检查"""
    
    @staticmethod
    def validate_question(question: str, max_length: int = 2000) -> bool:
        """验证用户问题"""
        if not question or not isinstance(question, str):
            raise ValueError("问题必须是非空字符串")
        
        if len(question) > max_length:
            raise ValueError(f"问题长度不能超过 {max_length} 字符")
        
        # 检查SQL注入风险
        dangerous_patterns = [
            "DROP", "DELETE", "INSERT", "UPDATE", "UNION", "EXEC"
        ]
        question_upper = question.upper()
        for pattern in dangerous_patterns:
            if pattern in question_upper:
                logger.warning(f"检测到可疑模式: {pattern}")
        
        return True
    
    @staticmethod
    def validate_sql(sql: str) -> bool:
        """验证 SQL 语句"""
        if not sql.upper().strip().startswith("SELECT"):
            raise ValueError("只允许 SELECT 查询")
        
        # 防止多语句执行
        if ";" in sql.split("--")[0]:  # 忽略注释中的分号
            raise ValueError("不允许执行多条 SQL 语句")
        
        return True


if __name__ == "__main__":
    # 测试混合查询引擎
    from infra.cache import create_cache_backend
    
    cache_backend = create_cache_backend("memory")
    cache_mgr = CacheManager(cache_backend)
    validator = QueryValidator()
    
    engine = HybridQueryEngine(cache_mgr, validator)
    
    print("=== 混合智能查询引擎 ===")
    print("引擎初始化成功")
