"""统一异常定义"""


class AppException(Exception):
    """应用基础异常"""
    def __init__(self, message: str, error_code: str = "UNKNOWN"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class ConfigException(AppException):
    """配置异常"""
    def __init__(self, message: str):
        super().__init__(message, "CONFIG_ERROR")


class LLMException(AppException):
    """LLM 调用异常"""
    def __init__(self, message: str):
        super().__init__(message, "LLM_ERROR")


class ToolException(AppException):
    """工具执行异常"""
    def __init__(self, message: str):
        super().__init__(message, "TOOL_ERROR")


class DatabaseException(AppException):
    """数据库操作异常"""
    def __init__(self, message: str):
        super().__init__(message, "DB_ERROR")


class ValidationException(AppException):
    """参数验证异常"""
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")
