import duckdb

from . import config
from .schema import init_schema


def connect(path=None) -> duckdb.DuckDBPyConnection:
    """Open (and create if needed) the DuckDB database with the schema applied."""
    path = path or config.DB_PATH
    if str(path) != ":memory:":
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    init_schema(con)
    return con
