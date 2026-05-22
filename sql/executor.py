import os

from dotenv import load_dotenv

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


class DBExecutor:

    _engine = None

    @classmethod
    def engine(cls):

        if cls._engine:
            return cls._engine

        load_dotenv()

        url = (
            f"mysql+pymysql://"
            f"{os.getenv('DB_USER')}:"
            f"{os.getenv('DB_PASS')}@"
            f"{os.getenv('DB_HOST')}:"
            f"{os.getenv('DB_PORT')}/"
            f"{os.getenv('DB_NAME')}"
        )

        cls._engine = create_engine(url)

        return cls._engine

    @classmethod
    def execute(
        cls,
        sql: str,
        params=None
    ):

        sql_lower = sql.lower().strip()

        if not sql_lower.startswith("select"):

            raise ValueError("只允许 SELECT")

        try:

            with cls.engine().connect() as conn:

                result = conn.execute(
                    text(sql),
                    params or {}
                )

                return [
                    dict(row._mapping)
                    for row in result.fetchall()
                ]

        except SQLAlchemyError as e:

            raise RuntimeError(str(e))