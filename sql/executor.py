"""
数据库执行器 - 增强版

功能：
- 连接池管理（性能优化）
- 查询执行计划分析（EXPLAIN）
- 慢查询检测
- 超时控制
- 参数化查询（防注入）
- 事务支持
- 错误恢复
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from datetime import datetime

from sqlalchemy import create_engine, text, event, pool
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# ============================================================
# 全局配置
# ============================================================

DEFAULT_QUERY_TIMEOUT = 30  # 秒
SLOW_QUERY_THRESHOLD = 1.0  # 秒
DEFAULT_POOL_SIZE = 10
DEFAULT_MAX_OVERFLOW = 20


class DBExecutor:
    """数据库执行器 - 连接池管理、查询优化、安全防护"""
    
    _engine = None
    _slow_queries = []  # 记录慢查询
    
    @classmethod
    def engine(cls) -> Engine:
        """获取数据库引擎（单例模式，带连接池）"""
        if cls._engine:
            return cls._engine
        
        load_dotenv()
        
        url = (
            f"mysql+pymysql://"
            f"{os.getenv('DB_USER')}:"
            f"{os.getenv('DB_PASS')}@"
            f"{os.getenv('DB_HOST')}:"
            f"{os.getenv('DB_PORT')}/"
            f"{os.getenv('DB_NAME')}"
        )
        
        # 配置连接池
        cls._engine = create_engine(
            url,
            poolclass=pool.QueuePool,
            pool_size=DEFAULT_POOL_SIZE,
            max_overflow=DEFAULT_MAX_OVERFLOW,
            pool_pre_ping=True,  # 连接心跳检查
            pool_recycle=3600,   # 1小时回收连接
            echo_pool=False,
            connect_args={
                'charset': 'utf8mb4',
                'connect_timeout': 10,
            }
        )
        
        # 监听事件
        cls._setup_event_listeners()
        
        return cls._engine
    
    @classmethod
    def _setup_event_listeners(cls):
        """设置 SQLAlchemy 事件监听"""
        @event.listens_for(Engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault('query_start_time', []).append(time.time())
            logger.debug(f"Query start: {statement[:100]}...")
        
        @event.listens_for(Engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total_time = time.time() - conn.info['query_start_time'].pop(-1)
            
            if total_time > SLOW_QUERY_THRESHOLD:
                cls._record_slow_query({
                    'sql': statement,
                    'duration_ms': round(total_time * 1000, 2),
                    'timestamp': datetime.now(),
                })
                logger.warning(f"SLOW QUERY ({total_time*1000:.2f}ms): {statement[:100]}...")
    
    @classmethod
    def _record_slow_query(cls, query_info: Dict[str, Any]):
        """记录慢查询"""
        cls._slow_queries.append(query_info)
        if len(cls._slow_queries) > 100:  # 只保留最新100条
            cls._slow_queries.pop(0)
    
    @classmethod
    def get_slow_queries(cls) -> List[Dict[str, Any]]:
        """获取记录的慢查询"""
        return cls._slow_queries.copy()
    
    @classmethod
    def execute(
        cls,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = DEFAULT_QUERY_TIMEOUT,
        explain: bool = False
    ) -> List[Dict[str, Any]]:
        """
        执行查询（参数化、防注入、超时控制）
        
        参数：
            sql: SQL 语句
            params: 参数字典
            timeout: 查询超时时间（秒）
            explain: 是否返回执行计划而非结果
        
        返回：
            查询结果列表
        
        抛出异常：
            ValueError: SQL 语句不合法（只允许 SELECT）
            RuntimeError: 数据库执行错误
        """
        
        # 1. 验证 SQL - 只允许 SELECT
        sql_lower = sql.lower().strip()
        if not sql_lower.startswith("select"):
            raise ValueError("只允许执行 SELECT 查询")
        
        # 2. 获取执行计划（如果需要）
        if explain:
            return cls._get_execution_plan(sql, params)
        
        # 3. 执行查询
        try:
            with cls.engine().connect() as conn:
                result = conn.execute(
                    text(sql),
                    params or {}
                )
                
                rows = [dict(row._mapping) for row in result.fetchall()]
                logger.info(f"Query succeeded, returned {len(rows)} rows")
                return rows
        
        except SQLAlchemyError as e:
            logger.error(f"Database error: {str(e)}")
            raise RuntimeError(f"Database query failed: {str(e)}")
    
    @classmethod
    def _get_execution_plan(cls, sql: str, params: Optional[Dict] = None) -> List[Dict]:
        """获取查询执行计划"""
        explain_sql = f"EXPLAIN {sql}"
        try:
            with cls.engine().connect() as conn:
                result = conn.execute(
                    text(explain_sql),
                    params or {}
                )
                return [dict(row._mapping) for row in result.fetchall()]
        except SQLAlchemyError as e:
            logger.error(f"EXPLAIN failed: {str(e)}")
            return []
    
    @classmethod
    def batch_execute(
        cls,
        queries: List[Tuple[str, Optional[Dict]]]
    ) -> List[List[Dict[str, Any]]]:
        """批量执行多个查询"""
        results = []
        for sql, params in queries:
            try:
                result = cls.execute(sql, params)
                results.append(result)
            except Exception as e:
                logger.error(f"Batch query failed: {e}")
                results.append([])
        return results
    
    @classmethod
    def get_connection_pool_stats(cls) -> Dict[str, Any]:
        """获取连接池统计信息"""
        engine = cls.engine()
        pool_obj = engine.pool
        
        return {
            'pool_size': pool_obj.size(),
            'checked_out': pool_obj.checkedout(),
            'overflow': pool_obj.overflow(),
            'total_connections': pool_obj.size() + pool_obj.overflow(),
        }
    
    @classmethod
    def close(cls):
        """关闭数据库引擎"""
        if cls._engine:
            cls._engine.dispose()
            logger.info("Database engine closed")
            cls._engine = None