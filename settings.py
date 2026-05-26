"""统一配置管理模块"""
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Settings:
    """应用配置管理（单例）"""

    # LLM 配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GPT_MODEL = os.getenv("GPT_MODEL", "qwen-plus")
    MODEL_URL = os.getenv("MODEL_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

    # 数据库配置
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASS = os.getenv("DB_PASS", "")

    # Flask 配置
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "True").lower() == "true"

    # 应用配置
    MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))
    MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "5"))

    @classmethod
    def get_db_url(cls):
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
    def validate(cls):
        """验证关键配置"""
        if not cls.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY 未设置")
        if not cls.DB_NAME:
            raise ValueError("DB_NAME 未设置")


# 单例实例
settings = Settings()
