import os
from dataclasses import dataclass, field

import psycopg
from dotenv import load_dotenv
from psycopg.rows import TupleRow

from sec_10k_rag.common.config import ROOT_DIR

DB_SERVICE = "db"
PG_TABLE = "chunks"
DEFAULT_HOST = "127.0.0.1"


@dataclass(frozen=True, kw_only=True)
class DbConnInfo:
    port: str
    dbname: str
    user: str
    password: str = field(repr=False)
    host: str = DEFAULT_HOST


def get_db_conn_info() -> DbConnInfo:
    load_dotenv(ROOT_DIR / ".env")
    return DbConnInfo(
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", DEFAULT_HOST),
    )


def connect(db: DbConnInfo) -> psycopg.Connection[TupleRow]:
    return psycopg.connect(
        host=db.host,
        port=db.port,
        dbname=db.dbname,
        user=db.user,
        password=db.password,
    )
