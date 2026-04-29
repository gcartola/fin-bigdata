import time
from typing import Optional
from urllib.parse import quote

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

    def _clean_path_parts(self, user_path: str) -> list[str]:
        cleaned = user_path.strip().rstrip("/")
        if cleaned.endswith(".*"):
            cleaned = cleaned[:-2]
        if cleaned.endswith("*"):
            cleaned = cleaned[:-1].rstrip(".").rstrip("/")

        parts = []
        for part in cleaned.split("."):
            value = part.strip().strip('"').strip("'").strip()
            if value:
                parts.append(value)
        return parts

    def _get_catalog_root_items(self) -> list[dict]:
        resp = self.session.get(self._api_url("catalog"))
        resp.raise_for_status()
        return resp.json().get("data", [])

    def list_catalogs(self) -> list[str]:
        catalogs = []
        for item in self._get_catalog_root_items():
            if item.get("containerType") in ("SPACE", "SOURCE", "FOLDER"):
                path = item.get("path") or []
                if path:
                    catalogs.append(".".join(path))
        return sorted(set(catalogs), key=str.lower)

    def _resolve_allowed_path(self, user_path: str) -> list[str]:
        requested_parts = self._clean_path_parts(user_path)
        requested = ".".join(requested_parts)
        requested_lower = requested.lower()

        try:
            for item in self._get_catalog_root_items():
                path = item.get("path") or []
                if not path:
                    continue
                full = ".".join(path)
                last = path[-1]
                if full.lower() == requested_lower or last.lower() == requested_lower:
                    return path
        except Exception as e:
            print(f"Aviso: não consegui resolver catálogo '{user_path}': {e}")

        return requested_parts

    def _get_catalog_by_path(self, path_parts: list[str]) -> dict:
        clean_parts = [p.strip().strip('"').strip("'").strip() for p in path_parts if p]
        path_encoded = "/".join(quote(p, safe="") for p in clean_parts)
        url = self._api_url(f"catalog/by-path/{path_encoded}")
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def list_catalog_items(self, path: str) -> list[dict]:
        path_parts = self._resolve_allowed_path(path)
        data = self._get_catalog_by_path(path_parts)
        items = []
        for child in data.get("children", []):
            child_path = child.get("path") or []
            if not child_path:
                continue
            ctype = child.get("type") or child.get("containerType") or child.get("entityType")
            dataset_type = child.get("datasetType")
            is_dataset = ctype == "DATASET" or bool(dataset_type)
            items.append({
                "name": child_path[-1],
                "path": ".".join(child_path),
                "sql_path": self._quote_sql_path(child_path),
                "type": "DATASET" if is_dataset else "CONTAINER",
                "description": dataset_type or ctype or "",
            })
        return sorted(items, key=lambda item: (item["type"], item["name"].lower()))

    def list_child_containers(self, path: str) -> list[str]:
        return [item["path"] for item in self.list_catalog_items(path) if item["type"] == "CONTAINER"]

    def list_datasets(self, path: str, recursive: bool = True) -> list[TableInfo]:
        path_parts = self._resolve_allowed_path(path)
        return self._list_path(path_parts) if recursive else [
            TableInfo(
                name=item["name"],
                full_path=item["sql_path"],
                columns=[],
                description=item["description"],
            )
            for item in self.list_catalog_items(path)
            if item["type"] == "DATASET"
        ]

    def _sql_path_parts(self, path_parts: list[str]) -> list[str]:
        parts = [p.strip().strip('"').strip("'").strip() for p in path_parts if p]

        if self.is_cloud and len(parts) > 1:
            allowed = {p.strip().strip('"').strip("'").lower() for p in self.allowed_paths if p.strip()}
            second = parts[1].strip().lower()

            if allowed and second in allowed:
                parts = parts[1:]
            elif "-" in parts[0] or " " in parts[0]:
                parts = parts[1:]

        return parts

    def _quote_sql_path(self, path_parts: list[str]) -> str:
        return ".".join(f'"{p}"' for p in self._sql_path_parts(path_parts))

    def _table_info_from_path(self, path: str, path_parts: list[str]) -> TableInfo:
        sql_path = path if '"' in path else self._quote_sql_path(path_parts)
        clean_name = self._clean_path_parts(path)[-1] if self._clean_path_parts(path) else sql_path
        return TableInfo(
            name=clean_name,
            full_path=sql_path,
            columns=[],
            description="Dataset selecionado no Dremio",
        )

    def list_tables(self) -> list[TableInfo]:
        tables = []
        if not self.allowed_paths:
            for item in self._get_catalog_root_items():
                if item.get("containerType") in ("SPACE", "SOURCE", "FOLDER"):
                    tables.extend(self._list_path(item["path"]))
        else:
            for path in self.allowed_paths:
                resolved = self._resolve_allowed_path(path)
                listed = self._list_path(resolved)
                if listed:
                    tables.extend(listed)
                    continue

                # When the UI passes a final selected view/dataset, there are no
                # child nodes to list. In that case list_tables must expose the
                # selected dataset itself so the agent can describe/sample/query it.
                if len(self._clean_path_parts(path)) >= 3 or len(resolved) >= 3:
                    tables.append(self._table_info_from_path(path, resolved))
        return tables

    def _list_path(self, path_parts: list[str]) -> list[TableInfo]:
        try:
            data = self._get_catalog_by_path(path_parts)
        except Exception as e:
            print(f"Aviso: não consegui listar {path_parts}: {e}")
            return []

        tables = []
        dataset_type = data.get("datasetType")
        if dataset_type and (data.get("path") or path_parts):
            dataset_path = data.get("path") or path_parts
            return [TableInfo(
                name=dataset_path[-1],
                full_path=self._quote_sql_path(dataset_path),
                columns=[],
                description=dataset_type or "Dataset do Dremio",
            )]

        for child in data.get("children", []):
            ctype = child.get("type") or child.get("containerType") or child.get("entityType")
            dataset_type = child.get("datasetType")
            child_path = child.get("path") or []

            if ctype == "DATASET" or dataset_type:
                if child_path:
                    tables.append(TableInfo(
                        name=child_path[-1],
                        full_path=self._quote_sql_path(child_path),
                        columns=[],
                        description=dataset_type or "Dataset do Dremio",
                    ))
            elif ctype in ("CONTAINER", "SPACE", "SOURCE", "FOLDER", "HOME"):
                if child_path:
                    tables.extend(self._list_path(child_path))
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
            "Importante: em Dremio Cloud, o project_id é usado na API, "
            "mas NÃO entra no caminho SQL. Use paths como "
            '"SPACE"."FOLDER"."VIEW_NAME". '
            "Suporta CTEs, window functions, regex, JSON functions."
        )
