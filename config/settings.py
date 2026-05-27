"""统一配置管理模块

支持多层配置：
1. 环境变量 (最高优先级)
2. .env 文件
3. 代码默认值

配置内容：
- LLM 模型配置
- 数据库连接
- Redis 缓存
- Flask 服务器
- 应用行为参数
- 安全与监控设置
"""

import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Settings:
    """应用配置管理（单例）
    
    企业级配置规范：
    - 所有敏感信息通过环境变量注入
    - 支持多环境（dev/staging/prod）
    - 配置验证与默认值管理
    """

    # ============================================================
    # LLM 配置
    # ============================================================
    
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GPT_MODEL = os.getenv("GPT_MODEL", "qwen-plus")
    MODEL_URL = os.getenv("MODEL_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # ============================================================
    # 数据库配置（MySQL）
    # ============================================================
    
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASS = os.getenv("DB_PASS", "")
    
    # 连接池配置
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    DB_QUERY_TIMEOUT = int(os.getenv("DB_QUERY_TIMEOUT", "30"))

    # ============================================================
    # Redis 缓存配置
    # ============================================================
    
    REDIS_ENABLED = os.getenv("REDIS_ENABLED", "True").lower() == "true"
    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    CACHE_TYPE = os.getenv("CACHE_TYPE", "redis")  # redis 或 memory
    CACHE_TTL_DEFAULT = int(os.getenv("CACHE_TTL_DEFAULT", "3600"))
    QUERY_CACHE_TTL = int(os.getenv("QUERY_CACHE_TTL", "3600"))
    PLAN_CACHE_TTL = int(os.getenv("PLAN_CACHE_TTL", "86400"))
    SESSION_TTL = int(os.getenv("SESSION_TTL", "86400"))

    # ============================================================
    # Flask 服务器配置
    # ============================================================
    
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    ENV = os.getenv("ENV", "development")

    # ============================================================
    # 应用行为配置
    # ============================================================
    
    MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))
    MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "5"))
    MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", "2000"))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

    # ============================================================
    # 查询优化配置
    # ============================================================
    
    SLOW_QUERY_THRESHOLD_MS = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "1000"))
    QUERY_RESULT_CACHE_ENABLED = os.getenv("QUERY_RESULT_CACHE_ENABLED", "True").lower() == "true"
    QUERY_PLAN_CACHE_ENABLED = os.getenv("QUERY_PLAN_CACHE_ENABLED", "True").lower() == "true"

    # ============================================================
    # 安全配置
    # ============================================================
    
    ENABLE_AUTH = os.getenv("ENABLE_AUTH", "False").lower() == "true"
    API_KEY_SECRET = os.getenv("API_KEY_SECRET", "")
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "False").lower() == "true"
    RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "60"))
    CORS_ENABLED = os.getenv("CORS_ENABLED", "True").lower() == "true"
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

    # ============================================================
    # 监控与日志配置
    # ============================================================
    
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_METRICS = os.getenv("ENABLE_METRICS", "True").lower() == "true"
    ENABLE_TRACING = os.getenv("ENABLE_TRACING", "False").lower() == "true"
    JAEGER_AGENT_HOST = os.getenv("JAEGER_AGENT_HOST", "localhost")
    JAEGER_AGENT_PORT = int(os.getenv("JAEGER_AGENT_PORT", "6831"))

    @classmethod
    def get_db_url(cls) -> str:
        """生成数据库连接 URL"""
        return (
            f"mysql+pymysql://"
            f"{cls.DB_USER}:"
            f"{cls.DB_PASS}@"
            f"{cls.DB_HOST}:"
            f"{cls.DB_PORT}/"
            f"{cls.DB_NAME}"
        )

    @classmethod
    def validate(cls) -> None:
        """验证关键配置"""
        errors = []
        
        # 必需配置
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY 未设置")
        if not cls.DB_NAME:
            errors.append("DB_NAME 未设置")
        
        # 数据库连接测试
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(cls.get_db_url())
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            errors.append(f"数据库连接失败: {e}")
        
        # Redis 连接测试（如果启用）
        if cls.REDIS_ENABLED:
            try:
                import redis
                from urllib.parse import urlparse
                
                parsed = urlparse(cls.REDIS_URL)
                r = redis.Redis(
                    host=parsed.hostname or "127.0.0.1",
                    port=parsed.port or 6379,
                    db=int(parsed.path.lstrip('/')) if parsed.path else 0,
                    socket_connect_timeout=5
                )
                r.ping()
            except Exception as e:
                errors.append(f"Redis 连接失败: {e}")
        
        if errors:
            raise ValueError("\n".join(errors))

    @classmethod
    def get_config_summary(cls) -> dict:
        """获取配置摘要（用于调试，不包含敏感信息）"""
        return {
            "environment": cls.ENV,
            "flask": {
                "host": cls.FLASK_HOST,
                "port": cls.FLASK_PORT,
                "debug": cls.FLASK_DEBUG,
            },
            "database": {
                "host": cls.DB_HOST,
                "port": cls.DB_PORT,
                "name": cls.DB_NAME,
                "pool_size": cls.DB_POOL_SIZE,
            },
            "cache": {
                "type": cls.CACHE_TYPE,
                "enabled": cls.REDIS_ENABLED,
                "default_ttl": cls.CACHE_TTL_DEFAULT,
            },
            "security": {
                "auth_enabled": cls.ENABLE_AUTH,
                "rate_limit_enabled": cls.RATE_LIMIT_ENABLED,
                "cors_enabled": cls.CORS_ENABLED,
            },
            "monitoring": {
                "metrics_enabled": cls.ENABLE_METRICS,
                "tracing_enabled": cls.ENABLE_TRACING,
                "log_level": cls.LOG_LEVEL,
            }
        }


# 单例实例
settings = Settings()
