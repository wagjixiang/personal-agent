"""
企业级 Schema Retrieval System

功能：
1. Schema 元数据管理
2. 表级 Retrieval
3. 字段级 Retrieval（Column Pruning）
4. Relation Expansion
5. Prompt Compression
6. Cache
7. 中文分词
8. 低 Token Schema Prompt

"""

from typing import (
    List,
    Dict,
    Set,
    Any,
    Optional,
    Tuple
)

import re
import jieba
from difflib import SequenceMatcher
from collections import defaultdict
from typing import List
from difflib import SequenceMatcher

from utils.db_table import (
    DATABASE_SCHEMA,
    RELATIONS
)

from schema.cache_manager import (
    get_cache_manager
)


# =========================================================
# Metadata Store
# =========================================================

class SchemaMetadataStore:
    """
    负责：
    - Schema 元数据管理
    - 表结构访问
    """

    def __init__(self):

        self._schema = DATABASE_SCHEMA
        self._relations = RELATIONS

    @property
    def schema(self):
        return self._schema

    @property
    def relations(self):
        return self._relations

    def get_table(self, table_name: str):

        return self._schema.get(table_name)

    def get_all_tables(self):

        return list(self._schema.keys())


# =========================================================
# Tokenizer
# =========================================================

class ChineseTokenizer:
    """
    中文分词器
    """

    @staticmethod
    def tokenize(text: str) -> List[str]:

        if not text:
            return []

        text = text.lower()

        # 去除特殊符号
        text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9]", " ", text)

        tokens = list(jieba.cut(text))

        # 清理空字符
        tokens = [
            token.strip()
            for token in tokens
            if token.strip()
        ]

        return tokens


# =========================================================
# Similarity Engine
# =========================================================

class SimilarityEngine:
    """
    轻量级关键词相似度引擎

    特点：
    1. 精确匹配优先
    2. 限制模糊匹配
    3. 去重
    4. 长度归一化
    5. 更快
    """

    # ==========================================
    # Stop Words
    # ==========================================

    STOP_WORDS = {
        "id",
        "name",
        "time",
        "create",
        "update",
        "data",
        "info"
    }

    # ==========================================
    # Similarity
    # ==========================================

    @classmethod
    def calculate_similarity(
        cls,
        query_tokens: List[str],
        doc_tokens: List[str],
        weight: float = 1.0
    ) -> float:

        if not query_tokens or not doc_tokens:
            return 0.0

        # ======================================
        # 去重 + 小写
        # ======================================

        query_set = {
            t.lower()
            for t in query_tokens
            if t.lower() not in cls.STOP_WORDS
        }

        doc_set = {
            t.lower()
            for t in doc_tokens
            if t.lower() not in cls.STOP_WORDS
        }

        if not query_set or not doc_set:
            return 0.0

        # ======================================
        # 精确匹配
        # ======================================

        exact_matches = query_set & doc_set

        exact_score = len(exact_matches) * 3.0

        # ======================================
        # Early Stop
        # ======================================

        if len(exact_matches) == len(query_set):

            return exact_score * weight

        # ======================================
        # 模糊匹配
        # ======================================

        fuzzy_score = 0.0

        unmatched_query = query_set - exact_matches
        unmatched_doc = doc_set - exact_matches

        for q in unmatched_query:

            best_ratio = 0.0

            for d in unmatched_doc:

                # 长度差太大直接跳过
                if abs(len(q) - len(d)) > 5:
                    continue

                ratio = SequenceMatcher(None, q, d).ratio()

                if ratio > best_ratio:
                    best_ratio = ratio

            # 只保留最佳匹配
            if best_ratio >= 0.8:
                fuzzy_score += best_ratio

        # ======================================
        # Length Normalization
        # ======================================

        normalization = (len(query_set) + len(doc_set)) ** 0.5

        final_score = (exact_score + fuzzy_score) / normalization

        return round(final_score * weight, 4)


# =========================================================
# Schema Retriever
# =========================================================

class SchemaRetriever:
    """
    表级 Retrieval
    """

    def __init__(
        self,
        metadata_store: SchemaMetadataStore
    ):

        self.store = metadata_store

        self.tokenizer = ChineseTokenizer()

        self.similarity_engine = SimilarityEngine()

        self._build_index()

    def _build_index(self):

        self.table_index = {}

        for table_name, table_info in self.store.schema.items():

            description = table_info.get(
                "description",
                ""
            )

            fields = table_info.get(
                "fields",
                {}
            )

            field_text = " ".join([
                f"{k} {v}"
                for k, v in fields.items()
            ])

            corpus = f"""
            {table_name}
            {description}
            {field_text}
            """

            self.table_index[table_name] = {
                "tokens": self.tokenizer.tokenize(corpus),
                "description": description,
                "fields": fields
            }

    def retrieve_tables(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:

        query_tokens = self.tokenizer.tokenize(query)

        scores = []

        for table_name, info in self.table_index.items():

            score = self.similarity_engine.calculate_similarity(
                query_tokens=query_tokens,
                doc_tokens=info["tokens"],
                weight=1.0
            )

            if score > 0:
                scores.append((table_name, score))

        # 表按照得分排序
        scores.sort(
            key=lambda x: x[1],
            reverse=True
        )

        return scores[:top_k]


# =========================================================
# Column Retriever
# =========================================================

class ColumnRetriever:
    """
    字段级 Retrieval
    """

    def __init__(
        self,
        metadata_store: SchemaMetadataStore
    ):

        self.store = metadata_store

        self.tokenizer = ChineseTokenizer()

        self.similarity_engine = SimilarityEngine()

    def retrieve_columns(
        self,
        query: str,
        table_name: str,
        top_k: int = 10
    ) -> List[str]:

        table_info = self.store.get_table(table_name)

        if not table_info:
            return []

        fields = table_info.get("fields", {})

        query_tokens = self.tokenizer.tokenize(query)

        scores = []

        for field_name, field_desc in fields.items():

            field_tokens = self.tokenizer.tokenize(
                f"{field_name} {field_desc}"
            )

            score = self.similarity_engine.calculate_similarity(
                query_tokens,
                field_tokens
            )

            if score > 0:
                scores.append((field_name, score))

        scores.sort(
            key=lambda x: x[1],
            reverse=True
        )

        return [
            field_name
            for field_name, _
            in scores[:top_k]
        ]


# =========================================================
# Relation Expander
# =========================================================

class RelationExpander:
    """
    表关系扩展器
    """

    def __init__(
        self,
        metadata_store: SchemaMetadataStore
    ):

        self.store = metadata_store

    def expand(
        self,
        tables: List[str],
        max_depth: int = 1
    ) -> Set[str]:

        result = set(tables)

        current_level = set(tables)

        for _ in range(max_depth):

            next_level = set()

            for relation in self.store.relations:

                left = relation["left_table"]
                right = relation["right_table"]

                if left in current_level:
                    next_level.add(right)

                if right in current_level:
                    next_level.add(left)

            current_level = next_level - result

            result.update(current_level)

        return result


# =========================================================
# Prompt Builder
# =========================================================

class SchemaPromptBuilder:
    """
    Schema Prompt 构建器
    """

    def __init__(
        self,
        metadata_store: SchemaMetadataStore
    ):

        self.store = metadata_store

    def build_prompt(
        self,
        tables: List[str],
        selected_columns: Dict[str, List[str]],
        compact: bool = True
    ) -> str:

        lines = []

        lines.append("## 数据库 Schema")

        for table_name in tables:

            table_info = self.store.get_table(table_name)

            if not table_info:
                continue

            description = table_info.get(
                "description",
                ""
            )

            lines.append("")
            lines.append(
                f"Table: {table_name}"
            )

            lines.append(
                f"Description: {description}"
            )

            lines.append("Columns:")

            fields = table_info.get("fields", {})

            selected = selected_columns.get(
                table_name,
                []
            )

            if not selected:
                selected = list(fields.keys())[:10]

            for field_name in selected:

                desc = fields.get(field_name, "")

                lines.append(
                    f"- {field_name}: {desc}"
                )

        # Relations
        relations = self._build_relations(tables)

        if relations:

            lines.append("")
            lines.append("## Relations")

            for rel in relations:

                lines.append(
                    f"{rel['left_table']}.{rel['left_field']} = "
                    f"{rel['right_table']}.{rel['right_field']}"
                )

        return "\n".join(lines)

    def _build_relations(
        self,
        tables: List[str]
    ):

        table_set = set(tables)

        results = []

        for relation in self.store.relations:

            if (
                relation["left_table"] in table_set
                and relation["right_table"] in table_set
            ):

                results.append(relation)

        return results


# =========================================================
# Facade Registry
# =========================================================

class SchemaRegistry:
    """
    Schema Retrieval 总入口
    """

    def __init__(self):

        self.store = SchemaMetadataStore()

        self.retriever = SchemaRetriever(
            self.store
        )

        self.column_retriever = ColumnRetriever(
            self.store
        )

        self.expander = RelationExpander(
            self.store
        )

        self.prompt_builder = SchemaPromptBuilder(
            self.store
        )

        self.cache = get_cache_manager()

    def retrieve(
        self,
        query: str,
        top_k_tables: int = 5,
        top_k_columns: int = 8,
        relation_depth: int = 1
    ) -> Dict[str, Any]:

        # ==============================
        # Cache
        # ==============================

        cached = self.cache.get_cached_tables(query)

        if cached:
            return cached

        # ==============================
        # Retrieve Tables
        # ==============================

        retrieved = self.retriever.retrieve_tables(
            query=query,
            top_k=top_k_tables
        )

        tables = [
            table_name
            for table_name, _
            in retrieved
        ]

        # ==============================
        # Relation Expansion
        # ==============================

        expanded_tables = self.expander.expand(
            tables,
            max_depth=relation_depth
        )

        expanded_tables = list(expanded_tables)

        # ==============================
        # Column Retrieval
        # ==============================

        selected_columns = {}

        for table_name in expanded_tables:

            columns = self.column_retriever.retrieve_columns(
                query=query,
                table_name=table_name,
                top_k=top_k_columns
            )

            selected_columns[table_name] = columns

        result = {
            "tables": expanded_tables,
            "selected_columns": selected_columns
        }

        self.cache.cache_tables(
            query,
            result
        )

        return result

    def build_schema_prompt(
        self,
        query: str
    ) -> str:

        retrieval_result = self.retrieve(query)

        return self.prompt_builder.build_prompt(
            tables=retrieval_result["tables"],
            selected_columns=retrieval_result["selected_columns"]
        )


# =========================================================
# Singleton
# =========================================================

_registry = None


def get_registry() -> SchemaRegistry:

    global _registry

    if _registry is None:
        _registry = SchemaRegistry()

    return _registry


# =========================================================
# Helper Functions
# =========================================================

def retrieve_schema(query: str):

    return get_registry().retrieve(query)


def build_schema_prompt(query: str):

    return get_registry().build_schema_prompt(query)


# =========================================================
# Debug
# =========================================================

if __name__ == "__main__":

    registry = get_registry()

    question = "统计每个学院的学生数量"

    result = registry.retrieve(question)

    print("=" * 50)
    print("Retrieval Result")
    print("=" * 50)

    print(result)

    print("\n")
    print("=" * 50)
    print("Prompt")
    print("=" * 50)

    prompt = registry.build_schema_prompt(
        question
    )

    print(prompt)