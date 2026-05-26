"""验证所有模块导入是否成功"""
import sys

def test_imports():
    """测试所有主要模块的导入"""
    tests = [
        ("exceptions", "from exceptions import AppException"),
        ("settings", "from settings import settings"),
        ("constants", "from constants import SYSTEM_PROMPT"),
        ("logger", "from logger import get_logger"),
        ("json_utils", "from json_utils import safe_json_loads"),
        ("tool_registry", "from tool_registry import tool, generate_openai_tools"),
        ("conversation_manager", "from conversation_manager import ConversationManager"),
        ("agent_executor", "from agent_executor import AgentExecutor"),
        ("chat_controller", "from chat_controller import chat_bp"),
        ("app", "from app import create_app"),
    ]
    
    print("=" * 60)
    print("验证模块导入")
    print("=" * 60)
    
    failed = []
    for name, import_stmt in tests:
        try:
            exec(import_stmt)
            print(f"✓ {name:30} OK")
        except Exception as e:
            print(f"✗ {name:30} FAILED: {str(e)[:60]}")
            failed.append((name, str(e)))
    
    print("=" * 60)
    
    if failed:
        print(f"\n❌ 发现 {len(failed)} 个失败的导入:\n")
        for name, error in failed:
            print(f"  {name}: {error}\n")
        return False
    else:
        print("\n✅ 所有模块导入成功！\n")
        return True


if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
