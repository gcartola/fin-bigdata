import re
from dataclasses import dataclass

from config import AnalyticsEngine, QueryResult, TableInfo


@dataclass
class _SourceTable:
    source: str
    table: TableInfo


class HybridEngine(AnalyticsEngine):
    """Lightweight multi-source engine for the MVP mixed mode.

    It does not try to perform a physical cross-engine JOIN yet. Instead, it
    exposes Dremio and spreadsheet tables to the same agent and routes each SQL
    statement to the right backend. This enables guided workflows such as:

    1. Query Dremio for a contract.
    2. Use returned CPF/name/status values to query the uploaded spreadsheet.
    3. Compare both results in the chat.
    """

    def __init__(self, dremio_engine: AnalyticsEngine | None = None, spreadsheet_engine: AnalyticsEngine | None = None):
        self.dremio_engine = dremio_engine
        self.spreadsheet_engine = spreadsheet_engine
        self._tables: dict[str, _SourceTable] = {}
        self.refresh_tables()

    def refresh_tables(self):
        self._tables = {}
        if self.dremio_engine:
            for table in self.dremio_engine.list_tables():
                self._add_table("dremio", table)
        if self.spreadsheet_engine:
            for table in self.spreadsheet_engine.list_tables():
                self._add_table("planilha", table)

    def _add_table(self, source: str, table: TableInfo):
        candidates = {
            table.name,
            table.full_path,
            table.full_path.replace('"', ''),
            table.full_path.split(".")[-1].strip('"'),
        }
        for candidate in candidates:
            if candidate:
                self._tables[candidate.lower()] = _SourceTable(source=source, table=table)

    def _find_table(self, table_name: str) -> _SourceTable:
        raw = table_name.strip()
        normalized = raw.strip('"').lower()
        if normalized in self._tables:
            return self._tables[normalized]

        raw_no_quotes = raw.replace('"', '').lower()
        if raw_no_quotes in self._tables:
            return self._tables[raw_no_quotes]

        for key, source_table in self._tables.items():
            if key.endswith(normalized) or normalized.endswith(key):
                return source_table

        available = "\n".join(f"- {t.table.full_path} ({t.source})" for t in self._tables.values())
        raise ValueError(f"Tabela não encontrada no modo combinado: {table_name}\n\nDisponíveis:\n{available}")

    def _route_query(self, query: str) -> AnalyticsEngine:
        query_lower = query.lower()

        dremio_hits = []
        spreadsheet_hits = []
        seen_ids = set()
        for source_table in self._tables.values():
            marker = id(source_table.table)
            if marker in seen_ids:
                continue
            seen_ids.add(marker)
            identifiers = {
                source_table.table.name.lower(),
                source_table.table.full_path.lower(),
                source_table.table.full_path.replace('"', '').lower(),
            }
            if any(identifier and identifier in query_lower for identifier in identifiers):
                if source_table.source == "dremio":
                    dremio_hits.append(source_table.table.full_path)
                else:
                    spreadsheet_hits.append(source_table.table.full_path)

        if dremio_hits and spreadsheet_hits:
            raise RuntimeError(
                "O modo combinado MVP ainda não executa JOIN físico entre Dremio e Planilha em uma única SQL. "
                "Faça em etapas: primeiro consulte uma fonte, use os valores retornados, depois consulte a outra."
            )

        if dremio_hits:
            return self.dremio_engine
        if spreadsheet_hits:
            return self.spreadsheet_engine

        # If the query references a quoted multi-part Dremio path, route to Dremio.
        if re.search(r'"[^".]+"\."[^".]+"\."[^".]+"', query):
            if self.dremio_engine:
                return self.dremio_engine

        # Fallback to spreadsheet for ad-hoc local SQL because DuckDB is more
        # permissive for temp analysis. If there is no spreadsheet, use Dremio.
        if self.spreadsheet_engine:
            return self.spreadsheet_engine
        if self.dremio_engine:
            return self.dremio_engine
        raise RuntimeError("Nenhuma fonte ativa no modo combinado.")

    def list_tables(self) -> list[TableInfo]:
        self.refresh_tables()
        unique = []
        seen = set()
        for source_table in self._tables.values():
            key = (source_table.source, source_table.table.full_path)
            if key in seen:
                continue
            seen.add(key)
            table = source_table.table
            unique.append(TableInfo(
                name=table.name,
                full_path=table.full_path,
                columns=table.columns,
                row_count=table.row_count,
                description=f"Fonte: {source_table.source}. {table.description or ''}".strip(),
            ))
        return unique

    def describe_table(self, table_name: str) -> TableInfo:
        source_table = self._find_table(table_name)
        engine = self.dremio_engine if source_table.source == "dremio" else self.spreadsheet_engine
        return engine.describe_table(source_table.table.full_path)

    def sample_rows(self, table_name: str, n: int = 5) -> QueryResult:
        source_table = self._find_table(table_name)
        engine = self.dremio_engine if source_table.source == "dremio" else self.spreadsheet_engine
        return engine.sample_rows(source_table.table.full_path, n=n)

    def run_sql(self, query: str) -> QueryResult:
        engine = self._route_query(query)
        return engine.run_sql(query)

    @property
    def engine_name(self) -> str:
        active = []
        if self.dremio_engine:
            active.append("Dremio")
        if self.spreadsheet_engine:
            active.append("Planilha")
        return " + ".join(active) + " (modo combinado)"

    @property
    def sql_dialect(self) -> str:
        return (
            "Modo combinado Dremio + DuckDB. Você enxerga tabelas de duas fontes. "
            "Tabelas com Fonte: dremio devem ser consultadas com SQL Dremio. "
            "Tabelas com Fonte: planilha devem ser consultadas com SQL DuckDB. "
            "Neste MVP, não faça JOIN físico entre Dremio e Planilha em uma única SQL. "
            "Faça análises em etapas: consulte Dremio, extraia valores relevantes, depois consulte a planilha, ou o inverso. "
            "Quando o usuário orientar uma relação por contrato, CPF, nome ou outra chave, use essa orientação para fazer consultas sequenciais."
        )
