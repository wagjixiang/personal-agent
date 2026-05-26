"""改进的日志管理模块"""
import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

# 日志目录（相对于仓库）
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
LOG_DIR = os.path.join(ROOT_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# 日志文件（按日期）
LOG_PATH = os.path.join(LOG_DIR, f"app.{datetime.now().strftime('%Y-%m-%d')}.log")


def get_logger(name: str = __name__):
    """
    获取配置好的 logger
    
    参数：
        name: logger 名称（通常为 __name__）
    
    返回：
        配置好的 logger 实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复配置
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # 格式化器
    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台处理器
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    
    # 文件处理器（按日期命名）
    file_handler = logging.FileHandler(LOG_PATH, encoding='utf-8')
    file_handler.setFormatter(fmt)
    
    # 添加处理器
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    
    return logger
