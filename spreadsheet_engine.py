import re
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import duckdb
from google.cloud import storage

from config import AnalyticsEngine, QueryResult, TableInfo


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _normalize_identifier(value: str) -> str:
    normalized = re.sub(r"\W+", "_", value.strip().lower()).strip("_")
    if not normalized:
        normalized = "table"
    if normalized[0].isdigit():
        normalized = f"t_{normalized}"
    return normalized


def _quote_identifier(value: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"Identificador inválido: {value}")
    return f'"{value}"'


def _parse_gcs_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc or not parsed.path:
        raise ValueError(f"URI GCS inválida: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


class SpreadsheetEngine(AnalyticsEngine):
    def __init__(self, db_path: str = ":memory:"):
        self.conn = duckdb.connect(db_path)
        self._loaded_tables: dict[str, str] = {}
        self._extensions_loaded: set[str] = set()
        self._staged_files: list[str] = []

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
            self.conn.execute(
                """
                CREATE OR REPLACE SECRET gcs_secret (
                    TYPE GCS,
                    KEY_ID ?,
                    SECRET ?
                )
                """,
                [hmac_key_id, hmac_secret],
            )

    def _stage_gcs_file(self, gcs_uri: str) -> str:
        bucket_name, object_name = _parse_gcs_uri(gcs_uri)
        suffix = Path(object_name).suffix
        staged = tempfile.NamedTemporaryFile(prefix="fin_bigdata_", suffix=suffix, delete=False)
        staged.close()

        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        if not blob.exists():
            raise FileNotFoundError(f"Arquivo GCS não encontrado: {gcs_uri}")

        blob.download_to_filename(staged.name)
        self._staged_files.append(staged.name)
        return staged.name

    def load_file(self, file_path: str, table_name: str | None = None) -> str:
        source_path = file_path
        is_gcs = file_path.startswith("gs://")

        if is_gcs:
            file_path = self._stage_gcs_file(file_path)

        if not Path(file_path).exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {source_path}")

        if table_name is None:
            base = source_path.split("/")[-1]
            table_name = Path(base).stem

        table_name = _normalize_identifier(table_name)
        quoted_table = _quote_identifier(table_name)
        ext = source_path.lower().split(".")[-1]

        if ext == "csv":
            self.conn.execute(
                f"CREATE OR REPLACE TABLE {quoted_table} AS "
                "SELECT * FROM read_csv_auto(?)",
                [file_path],
            )
        elif ext in ("xlsx", "xls"):
            self._ensure_extension("excel")
            self.conn.execute(
                f"CREATE OR REPLACE TABLE {quoted_table} AS "
                "SELECT * FROM read_xlsx(?)",
                [file_path],
            )
        elif ext == "parquet":
            self.conn.execute(
                f"CREATE OR REPLACE TABLE {quoted_table} AS "
                "SELECT * FROM read_parquet(?)",
                [file_path],
            )
        else:
            raise ValueError(f"Formato não suportado: {ext}")

        self._loaded_tables[table_name] = source_path
        return table_name

    def list_tables(self) -> list[TableInfo]:
        return [self.describe_table(name) for name in self._loaded_tables]

    def describe_table(self, table_name: str) -> TableInfo:
        table_name = _normalize_identifier(table_name)
        quoted_table = _quote_identifier(table_name)
        schema_rows = self.conn.execute(f"DESCRIBE {quoted_table}").fetchall()
        columns = [
            {"name": row[0], "type": row[1], "nullable": row[2] == "YES"}
            for row in schema_rows
        ]
        row_count = self.conn.execute(f"SELECT COUNT(*) FROM {quoted_table}").fetchone()[0]
        return TableInfo(
            name=table_name,
            full_path=quoted_table,
            columns=columns,
            row_count=row_count,
            description=f"Carregada de: {self._loaded_tables.get(table_name, '?')}",
        )

    def sample_rows(self, table_name: str, n: int = 5) -> QueryResult:
        table_name = _normalize_identifier(table_name)
        return self.run_sql(f"SELECT * FROM {_quote_identifier(table_name)} LIMIT {int(n)}")

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
