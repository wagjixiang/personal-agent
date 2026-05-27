'''
Author: Wang Jixiang
Date: 2026-05-14 17:28:33
LastEditors: Wang Jixiang
LastEditTime: 2026-05-15 18:33:18
Description: 
'''
import json
from datetime import date, datetime

from server.db_server import run_query

def json_serializer(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

if __name__ == "__main__":

    question = "我想找一个最年轻的学生来帮我做件事情，应该找谁？"

    result = run_query(question)

    print("\n============== RESULT ==============\n")

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=json_serializer
        )
    )