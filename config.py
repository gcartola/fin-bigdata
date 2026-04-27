from dataclasses import dataclass
from typing import Optional


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    row_count: int
    bytes_scanned: Optional[int] = None
    execution_time_ms: Optional[int] = None
    sql_executed: Optional[str] = None


@dataclass
class TableInfo:
    name: str
    full_path: str
    columns: list[dict]
    row_count: Optional[int] = None
    description: Optional[str] = None
