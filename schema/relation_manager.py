'''
Author: Wang Jixiang
Date: 2026-05-21 18:15:04
LastEditors: Wang Jixiang
LastEditTime: 2026-05-21 18:15:18
Description: 
'''
from utils.db_table import RELATIONS


def build_relation_text() -> str:

    lines = []

    for r in RELATIONS:

        lines.append(
            f"{r['left_table']}.{r['left_field']} "
            f"= "
            f"{r['right_table']}.{r['right_field']}"
        )

    return "\n".join(lines)


def get_relations():

    return RELATIONS