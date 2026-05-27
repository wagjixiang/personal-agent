'''
查询规划 Agent
企业级版本

功能：
1. Schema Retrieval
2. Prompt Injection
3. Query Planning
4. SQL Build
5. SQL Validation
6. SQL Execution
7. Multi-task Query
'''

import json
import logging

from llm.llm_api import get_answer

from models.query_plan import (
    QueryTaskList
)

from schema.planner_prompt import (
    build_planner_prompt
)

from schema.schema_manager import (
    get_schema_prompt
)

from schema.relation_manager import (
    build_relation_text
)

from sql.validator import (
    validate_plan
)

from sql.builder import (
    build_sql
)

from sql.executor import (
    DBExecutor
)

from utils.json_utils import (
    safe_json_loads
)

logger = logging.getLogger(__name__)


class QueryAgent:

    # =====================================================
    # Build Query Tasks
    # =====================================================

    @classmethod
    def build_query_tasks(
        cls,
        question: str
    ) -> QueryTaskList:
        """
        构建查询任务

        Pipeline:
        1. Schema Retrieval
        2. Prompt Build
        3. LLM Planning
        4. Parse QueryPlan
        """

        # ==============================================
        # Schema Retrieval
        # ==============================================

        try:

            schema_prompt = get_schema_prompt(question)

            logger.info(
                f"Schema retrieval success: {question[:50]}"
            )

        except Exception as e:

            logger.exception(
                "Schema retrieval failed"
            )

            raise RuntimeError(
                f"Schema retrieval failed: {e}"
            )

        # ==============================================
        # Relation Text
        # ==============================================

        relation_text = build_relation_text()

        # ==============================================
        # Planner Prompt
        # ==============================================

        prompt = build_planner_prompt(
            question=question,

            schema_json=schema_prompt,

            relation_text=relation_text
        )

        logger.debug(
            f"Planner Prompt:\n{prompt}"
        )

        # ==============================================
        # LLM Planning
        # ==============================================

        result = get_answer(prompt)

        # ==============================================
        # JSON Parse
        # ==============================================

        if isinstance(result, str):

            result = safe_json_loads(result)

        logger.debug(
            f"Planner Result: {result}"
        )

        # ==============================================
        # QueryTask Parse
        # ==============================================

        return QueryTaskList.model_validate(
            result
        )

    # =====================================================
    # Run
    # =====================================================

    @classmethod
    def run(
        cls,
        question: str
    ):
        """
        执行 Query Agent
        """

        logger.info(f"QueryAgent started: {question}")

        tasks = cls.build_query_tasks(question)

        results = []

        for task in tasks.tasks:

            try:

                logger.info(f"Executing task: {task.name}")

                # ==================================
                # Query Plan
                # ==================================

                plan = task.plan

                # ==================================
                # Validate Query Plan
                # ==================================

                validate_plan(plan)

                # ==================================
                # Build SQL
                # ==================================

                sql, params = build_sql(plan)

                logger.info(f"Generated SQL: {sql}")

                # ==================================
                # Execute SQL
                # ==================================

                data = DBExecutor.execute(sql, params)

                # ==================================
                # Result
                # ==================================

                results.append({

                    "task_name": task.name,

                    "success": True,

                    "sql": sql,

                    "params": params,

                    "rows": len(data),

                    "data": data
                })

            except Exception as e:

                logger.exception(f"Task failed: {task.name}")

                results.append({

                    "task_name": task.name,

                    "success": False,

                    "error": str(e)
                })

        return results