import time
from typing import Optional

import requests

from config import AnalyticsEngine, QueryResult, TableInfo


class DremioEngine(AnalyticsEngine):
    def __init__(
        self,
        host: str,
        pat: str,
        project_id: Optional[str] = None,
        is_cloud: bool = False,
        allowed_paths: Optional[list[str]] = None,
    ):
        self.host = host.rstrip("/")
        self.pat = pat
        self.project_id = project_id
        self.is_cloud = is_cloud
        self.allowed_paths = allowed_paths or []
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
        })

    def _api_url(self, path: str) -> str:
        if self.is_cloud:
            return f"{self.host}/v0/projects/{self.project_id}/{path.lstrip('/')}"
        return f"{self.host}/api/v3/{path.lstrip('/')}"

    def _sql_url(self) -> str:
        if self.is_cloud:
            return f"{self.host}/v0/projects/{self.project_id}/sql"
        return f"{self.host}/api/v3/sql"

    def list_tables(self) -> list[TableInfo]:
        tables = []
        if not self.allowed_paths:
            resp = self.session.get(self._api_url("catalog"))
            resp.raise_for_status()
            for item in resp.json().get("data", []):
                if item.get("containerType") in ("SPACE", "SOURCE", "FOLDER"):
                    tables.extend(self._list_path(item["path"]))
        else:
            for path in self.allowed_paths:
                tables.extend(self._list_path(path.split(".")))
        return tables

    def _list_path(self, path_parts: list[str]) -> list[TableInfo]:
        path_encoded = "/".join(path_parts)
        url = self._api_url(f"catalog/by-path/{path_encoded}")
        try:
            resp = self.session.get(url)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"Aviso: não consegui listar {path_parts}: {e}")
            return []

        tables = []
        for child in data.get("children", []):
            ctype = child.get("type")
            if ctype == "DATASET":
                tables.append(TableInfo(
                    name=child["path"][-1],
                    full_path=".".join(f'"{p}"' for p in child["path"]),
                    columns=[],
                    description=child.get("datasetType", ""),
                ))
            elif ctype == "CONTAINER":
                tables.extend(self._list_path(child["path"]))
        return tables

    def describe_table(self, table_full_path: str) -> TableInfo:
        result = self.run_sql(f"SELECT * FROM {table_full_path} LIMIT 0")
        columns = [{"name": col, "type": "?", "nullable": True} for col in result.columns]
        return TableInfo(
            name=table_full_path.split(".")[-1].strip('"'),
            full_path=table_full_path,
            columns=columns,
            description="Dataset do Dremio",
        )

    def sample_rows(self, table_full_path: str, n: int = 5) -> QueryResult:
        return self.run_sql(f"SELECT * FROM {table_full_path} LIMIT {n}")

    def run_sql(self, query: str) -> QueryResult:
        start = time.time()
        submit_resp = self.session.post(self._sql_url(), json={"sql": query})
        submit_resp.raise_for_status()
        job_id = submit_resp.json()["id"]

        job_url = self._api_url(f"job/{job_id}")
        while True:
            job_resp = self.session.get(job_url)
            job_resp.raise_for_status()
            state = job_resp.json()["jobState"]
            if state == "COMPLETED":
                break
            if state in ("FAILED", "CANCELED"):
                error = job_resp.json().get("errorMessage", "sem detalhe")
                raise RuntimeError(f"Job Dremio falhou: {error}\n\nSQL:\n{query}")
            time.sleep(0.3)

        results_url = self._api_url(f"job/{job_id}/results?offset=0&limit=500")
        results_resp = self.session.get(results_url)
        results_resp.raise_for_status()
        data = results_resp.json()

        schema = data.get("schema", [])
        columns = [field["name"] for field in schema]
        rows_raw = data.get("rows", [])
        rows = [[row.get(col) for col in columns] for row in rows_raw]

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=data.get("rowCount", len(rows)),
            execution_time_ms=int((time.time() - start) * 1000),
            sql_executed=query,
        )

    @property
    def engine_name(self) -> str:
        return f"Dremio ({'Cloud' if self.is_cloud else 'on-prem'})"

    @property
    def sql_dialect(self) -> str:
        return (
            "Dremio SQL (Apache Calcite, ANSI SQL). "
            "Funções de data: DATE_TRUNC, EXTRACT, DATE_ADD/SUB. "
            "Importante: nomes de tabelas devem vir entre aspas duplas: "
            '"workspace"."folder"."view_name". '
            "Suporta CTEs, window functions, regex, JSON functions."
        )
