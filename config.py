from abc import ABC, abstractmethod
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

    def to_markdown(self, max_rows: int = 20) -> str:
        if not self.rows:
            return "_(sem resultados)_"
        header = "| " + " | ".join(self.columns) + " |"
        sep = "|" + "|".join(["---"] * len(self.columns)) + "|"
        body_rows = self.rows[:max_rows]
        body = "\n".join(
            "| " + " | ".join(str(c) if c is not None else "NULL" for c in row) + " |"
            for row in body_rows
        )
        suffix = f"\n\n_(mostrando {max_rows} de {self.row_count} linhas)_" if len(self.rows) > max_rows else ""
        return f"{header}\n{sep}\n{body}{suffix}"


@dataclass
class TableInfo:
    name: str
    full_path: str
    columns: list[dict]
    row_count: Optional[int] = None
    description: Optional[str] = None


class AnalyticsEngine(ABC):
    @abstractmethod
    def list_tables(self) -> list[TableInfo]: ...

    @abstractmethod
    def describe_table(self, table_name: str) -> TableInfo: ...

    @abstractmethod
    def sample_rows(self, table_name: str, n: int = 5) -> QueryResult: ...

    @abstractmethod
    def run_sql(self, query: str) -> QueryResult: ...

    @property
    @abstractmethod
    def engine_name(self) -> str: ...

    @property
    @abstractmethod
    def sql_dialect(self) -> str: ...
