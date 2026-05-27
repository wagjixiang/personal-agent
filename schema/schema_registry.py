"""
Schema Registry - 表元数据管理和优化系统
用途：
1. 集中管理所有数据库表的元数据
2. 提供智能表查询（按关键词推断需要的表）
3. 生成精简的 schema 信息，减少 Token 消耗
"""

from typing import List, Dict, Set, Any
from utils.db_table import DATABASE_SCHEMA, RELATIONS
import re


class SchemaRegistry:
    """表元数据注册表"""
    
    def __init__(self):
        self._schema = DATABASE_SCHEMA
        self._relations = RELATIONS
        self._build_index()
    
    def _build_index(self):
        """构建表名和字段的索引，用于快速查询"""
        self._table_keywords = {}
        self._field_keywords = {}
        
        for table_name, table_info in self._schema.items():
            # 表名索引
            self._table_keywords[table_name] = {
                "description": table_info.get("description", ""),
                "fields": list(table_info.get("fields", {}).keys())
            }
            
            # 字段索引：字段名 -> (表名, 字段描述)
            for field_name, field_desc in table_info.get("fields", {}).items():
                if field_name not in self._field_keywords:
                    self._field_keywords[field_name] = []
                self._field_keywords[field_name].append({
                    "table": table_name,
                    "description": field_desc
                })
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """获取单个表的详细信息"""
        if table_name not in self._schema:
            return None
        return self._schema[table_name]
    
    def get_all_tables(self) -> List[str]:
        """获取所有表名"""
        return list(self._schema.keys())
    
    def infer_tables_from_query(self, user_query: str) -> List[str]:
        """
        智能推断用户查询需要哪些表
        
        算法：
        1. 关键词匹配：检查描述和字段名
        2. 关系推断：如果需要表A，看是否需要表B（通过外键关系）
        3. 返回按相关度排序的表列表
        
        这样可以避免一次性传递所有表 schema，大幅减少 Token 消耗
        """
        query_lower = user_query.lower()
        
        # 第一步：按关键词找到匹配的表
        matches = {}
        
        for table_name, table_info in self._schema.items():
            relevance_score = 0
            
            # 表描述匹配
            description = table_info.get("description", "").lower()
            if self._calculate_similarity(query_lower, description) > 0:
                relevance_score += 10
            
            # 字段名/字段描述匹配
            for field_name, field_desc in table_info.get("fields", {}).items():
                field_lower = f"{field_name} {field_desc}".lower()
                similarity = self._calculate_similarity(query_lower, field_lower)
                if similarity > 0:
                    relevance_score += similarity
            
            if relevance_score > 0:
                matches[table_name] = relevance_score
        
        # 第二步：根据关系扩展（例如：查询学生信息可能需要学院信息）
        extended_tables = set(matches.keys())
        for table in list(extended_tables):
            related = self._get_related_tables(table)
            # 只添加直接相关的表，不要过度扩展
            extended_tables.update(related)
        
        # 返回按相关度排序的表，最相关的在前
        sorted_tables = sorted(
            matches.keys(),
            key=lambda t: matches[t],
            reverse=True
        )
        
        # 添加相关表（排在后面，优先级低）
        for table in extended_tables:
            if table not in sorted_tables:
                sorted_tables.append(table)
        
        return sorted_tables if sorted_tables else []
    
    def _calculate_similarity(self, query: str, text: str) -> float:
        """计算查询和文本的相似度"""
        score = 0
        query_words = set(query.split())
        text_words = set(text.split())
        
        # 词汇交集分数
        intersection = query_words & text_words
        if intersection:
            score += len(intersection)
        
        # 子串匹配分数
        if query in text:
            score += 5
        
        return score
    
    def _get_related_tables(self, table_name: str) -> Set[str]:
        """获取与某个表直接相关的表（通过外键关系）"""
        related = set()
        
        for relation in self._relations:
            if relation["left_table"] == table_name:
                related.add(relation["right_table"])
            elif relation["right_table"] == table_name:
                related.add(relation["left_table"])
        
        return related
    
    def get_minimal_schema(self, table_names: List[str]) -> Dict[str, Any]:
        """
        生成精简的 schema 信息
        只包含指定表的信息，用于传递给 LLM
        
        返回格式：
        {
            "tables": {
                "tb_student": {
                    "description": "...",
                    "fields": {...}
                }
            },
            "relations": [...]  # 仅包含相关的关系
        }
        """
        result = {
            "tables": {},
            "relations": []
        }
        
        table_set = set(table_names)
        
        # 添加表信息
        for table_name in table_names:
            if table_name in self._schema:
                result["tables"][table_name] = self._schema[table_name]
        
        # 添加相关的关系信息
        for relation in self._relations:
            if (relation["left_table"] in table_set and 
                relation["right_table"] in table_set):
                result["relations"].append(relation)
        
        return result
    
    def get_schema_prompt(self, user_query: str) -> str:
        """
        为 LLM 生成优化的 schema 提示信息
        
        流程：
        1. 智能推断需要的表
        2. 生成精简 schema
        3. 格式化为 prompt
        
        这样每次查询只传递必要的表信息，大幅减少 Token
        """
        # 推断需要的表
        table_names = self.infer_tables_from_query(user_query)
        
        if not table_names:
            # 如果没有推断到表，返回提示
            return "未找到匹配的表。请检查查询内容。"
        
        # 生成精简 schema
        schema_info = self.get_minimal_schema(table_names)
        
        # 格式化为 prompt
        prompt = "## 数据库 Schema 信息\n\n"
        
        for table_name, table_info in schema_info["tables"].items():
            prompt += f"### {table_name}\n"
            prompt += f"描述：{table_info.get('description', '')}\n"
            prompt += "字段：\n"
            
            for field_name, field_desc in table_info.get("fields", {}).items():
                prompt += f"  - {field_name}: {field_desc}\n"
            
            prompt += "\n"
        
        if schema_info["relations"]:
            prompt += "### 表关系\n"
            for relation in schema_info["relations"]:
                prompt += (
                    f"{relation['left_table']}.{relation['left_field']} = "
                    f"{relation['right_table']}.{relation['right_field']}\n"
                )
        
        return prompt


# 全局实例
_registry = None


def get_registry() -> SchemaRegistry:
    """获取全局 SchemaRegistry 实例"""
    global _registry
    if _registry is None:
        _registry = SchemaRegistry()
    return _registry


# 便捷函数
def infer_tables(query: str) -> List[str]:
    """推断查询需要的表"""
    return get_registry().infer_tables_from_query(query)


def get_schema_for_llm(query: str) -> str:
    """为 LLM 获取优化的 schema 信息"""
    return get_registry().get_schema_prompt(query)


def get_minimal_schema_dict(table_names: List[str]) -> Dict[str, Any]:
    """获取精简的 schema 字典"""
    return get_registry().get_minimal_schema(table_names)
