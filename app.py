"""
Personal Agent - 主应用入口

Flask 应用配置和初始化
"""
from flask import Flask, render_template

from logger import get_logger
from settings import settings
from chat_controller import chat_bp

logger = get_logger(__name__)


# ============================================================
# Flask 应用初始化
# ============================================================

def create_app() -> Flask:
    """
    创建 Flask 应用实例
    
    返回：
        Flask 应用对象
    """
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='templates'
    )
    
    # 配置
    app.config['JSON_AS_ASCII'] = False
    app.config['JSON_SORT_KEYS'] = False
    
    # 注册蓝图
    app.register_blueprint(chat_bp)
    
    # 首页路由
    @app.route('/')
    def home():
        """首页"""
        return render_template('index.html')
    
    # 健康检查
    @app.route('/health')
    def health():
        """健康检查端点"""
        return {
            "status": "ok",
            "version": "2.0"
        }
    
    logger.info("Flask app created successfully")
    
    return app


# ============================================================
# 主程序
# ============================================================

if __name__ == "__main__":
    try:
        # 验证配置
        settings.validate()
        logger.info("Configuration validated successfully")
        
        # 创建应用
        app = create_app()
        
        # 启动服务
        logger.info(
            f"Starting server at {settings.FLASK_HOST}:{settings.FLASK_PORT} "
            f"(debug={settings.FLASK_DEBUG})"
        )
        
        app.run(
            host=settings.FLASK_HOST,
            port=settings.FLASK_PORT,
            debug=settings.FLASK_DEBUG
        )
    
    except Exception as e:
        logger.exception(f"Failed to start application: {e}")
        raise
