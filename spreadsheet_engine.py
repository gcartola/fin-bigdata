import time
from pathlib import Path

import duckdb

from config import AnalyticsEngine, QueryResult, TableInfo


class SpreadsheetEngine(AnalyticsEngine):
    def __init__(self, db_path: str = ":memory:"):
        self.conn = duckdb.connect(db_path)
        self._loaded_tables: dict[str, str] = {}
        self._extensions_loaded: set[str] = set()

    def _ensure_extension(self, name: str):
        if name in self._extensions_loaded:
            return
        try:
            self.conn.execute(f"INSTALL {name}; LOAD {name};")
            self._extensions_loaded.add(name)
        except Exception as e:
            raise RuntimeError(
                f"Não consegui carregar extensão DuckDB '{name}': {e}\n"
                f"Verifique conectividade com extensions.duckdb.org"
            )

    def configure_gcs(self, hmac_key_id: str | None = None, hmac_secret: str | None = None):
        self._ensure_extension("httpfs")
        if hmac_key_id and hmac_secret:
            self.conn.execute(f"""
                CREATE OR REPLACE SECRET gcs_secret (
                    TYPE GCS,
                    KEY_ID '{hmac_key_id}',
                    SECRET '{hmac_secret}'
                )
            """)

    def load_file(self, file_path: str, table_name: str | None = None) -> str:
        is_gcs = file_path.startswith("gs://")

        if is_gcs:
            self._ensure_extension("httpfs")

        if not is_gcs and not Path(file_path).exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

        if table_name is None:
            base = file_path.split("/")[-1]
            table_name = Path(base).stem.lower().replace("-", "_").replace(" ", "_")

        ext = file_path.lower().split(".")[-1]

        if ext == "csv":
            self.conn.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                f"SELECT * FROM read_csv_auto('{file_path}')"
            )
        elif ext in ("xlsx", "xls"):
            self._ensure_extension("excel")
            self.conn.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                f"SELECT * FROM read_xlsx('{file_path}')"
            )
        elif ext == "parquet":
            self.conn.execute(
                f"CREATE OR REPLACE TABLE {table_name} AS "
                f"SELECT * FROM read_parquet('{file_path}')"
            )
        else:
            raise ValueError(f"Formato não suportado: {ext}")

        self._loaded_tables[table_name] = file_path
        return table_name

    def list_tables(self) -> list[TableInfo]:
        return [self.describe_table(name) for name in self._loaded_tables]

    def describe_table(self, table_name: str) -> TableInfo:
        schema_rows = self.conn.execute(f"DESCRIBE {table_name}").fetchall()
        columns = [
            {"name": row[0], "type": row[1], "nullable": row[2] == "YES"}
            for row in schema_rows
        ]
        row_count = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        return TableInfo(
            name=table_name,
            full_path=table_name,
            columns=columns,
            row_count=row_count,
            description=f"Carregada de: {self._loaded_tables.get(table_name, '?')}",
        )

    def sample_rows(self, table_name: str, n: int = 5) -> QueryResult:
        return self.run_sql(f"SELECT * FROM {table_name} LIMIT {n}")

    def run_sql(self, query: str) -> QueryResult:
        start = time.time()
        try:
            result = self.conn.execute(query)
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            return QueryResult(
                columns=columns,
                rows=[list(row) for row in rows],
                row_count=len(rows),
                execution_time_ms=int((time.time() - start) * 1000),
                sql_executed=query,
            )
        except Exception as e:
            raise RuntimeError(f"Erro na query: {e}\n\nSQL:\n{query}")

    @property
    def engine_name(self) -> str:
        return "DuckDB (planilhas locais ou GCS)"

    @property
    def sql_dialect(self) -> str:
        return (
            "DuckDB SQL (PostgreSQL-like). Funções úteis: "
            "DATE_TRUNC('month', col), STRFTIME, REGEXP_MATCHES, LIST_AGG, "
            "PIVOT, UNPIVOT. Suporta CTEs e window functions completas."
        )
