'''
Author: Wang Jixiang
Date: 2026-05-21 18:29:58
LastEditors: Wang Jixiang
LastEditTime: 2026-05-21 18:45:49
Description: 
'''
import json

from llm.chat_api import get_answer


def safe_json_loads(raw: str):

    raw = (
        raw
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    try:

        return json.loads(raw)

    except Exception:

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

        repaired = (
            repaired
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        return json.loads(repaired)