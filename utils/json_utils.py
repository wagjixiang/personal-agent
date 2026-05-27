"""JSON 处理工具（改进版）"""
import json
from typing import Any, Dict

from llm.llm_api import get_answer


def safe_json_loads(raw: str) -> Dict[str, Any]:
    """
    安全的 JSON 解析，失败时自动修复
    
    参数：
        raw: 原始 JSON 字符串
    
    返回：
        解析后的字典对象
    """
    # 清理 markdown 标记
    raw = (
        raw
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    try:
        return json.loads(raw)
    except Exception:
        # 使用 LLM 修复 JSON
        repair_prompt = f"""
        你是 JSON 修复助手。
        
        请修复下面的 JSON。
        
        要求：
        1. 只返回 JSON
        2. 不要 markdown
        3. 不要解释
        4. 保持原始字段结构
        
        待修复 JSON:
        {raw}
        """

        repaired = get_answer(repair_prompt)

        # 再次清理
        repaired = (
            repaired
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        return json.loads(repaired)


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    安全的 JSON 序列化
    
    参数：
        obj: 要序列化的对象
        **kwargs: 传递给 json.dumps 的参数
    
    返回：
        JSON 字符串
    """
    kwargs.setdefault('ensure_ascii', False)
    kwargs.setdefault('indent', 2)
    return json.dumps(obj, **kwargs)