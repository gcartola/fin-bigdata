import base64
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Optional

import requests

from dremio_engine import DremioEngine


@dataclass(frozen=True)
class AuthenticatedUser:
    email: str
    user_id: str


class DremioPATAuthenticator:
    """Valida um PAT do Dremio e resolve a identidade persistente do usuário.

    O PAT é usado apenas como credencial temporária de desbloqueio. A identidade
    persistente do app é o e-mail resolvido no Dremio. O token nunca deve ser
    salvo em banco, log ou mensagem de erro exibida ao usuário.
    """

    def __init__(self, host: str, project_id: str, is_cloud: bool = True):
        self.host = host.rstrip("/")
        self.project_id = project_id
        self.is_cloud = is_cloud

    def authenticate(self, pat: str) -> AuthenticatedUser:
        clean_pat = (pat or "").strip()
        if not clean_pat:
            raise ValueError("Informe um PAT do Dremio.")

        engine = DremioEngine(
            host=self.host,
            pat=clean_pat,
            project_id=self.project_id,
            is_cloud=self.is_cloud,
            allowed_paths=[],
        )

        # Validação objetiva do PAT: se o Dremio negar, a exceção sobe como erro
        # de autenticação tratado pela UI. Também evita aceitar token bem formado,
        # mas inválido/revogado.
        engine.list_catalogs()

        email = self._resolve_email(clean_pat, engine)
        user_id = build_user_id(email)
        return AuthenticatedUser(email=email, user_id=user_id)

    def _resolve_email(self, pat: str, engine: DremioEngine) -> str:
        candidates = [
            self._email_from_optional_endpoint(pat),
            self._email_from_common_user_endpoints(pat),
            self._email_from_pat_payload(pat),
            self._email_from_current_user_sql(engine),
        ]
        for candidate in candidates:
            email = normalize_email(candidate)
            if email:
                return email
        raise RuntimeError(
            "PAT validado, mas não consegui resolver o e-mail do usuário no Dremio. "
            "Configure DREMIO_USER_EMAIL_ENDPOINT ou ajuste o endpoint de perfil do Dremio."
        )

    def _headers(self, pat: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
        }

    def _email_from_optional_endpoint(self, pat: str) -> Optional[str]:
        endpoint = os.getenv("DREMIO_USER_EMAIL_ENDPOINT", "").strip()
        if not endpoint:
            return None
        return self._email_from_endpoint(endpoint, pat)

    def _email_from_common_user_endpoints(self, pat: str) -> Optional[str]:
        if self.is_cloud:
            endpoints = [
                f"{self.host}/v0/user",
                f"{self.host}/v0/users/me",
                f"{self.host}/v0/projects/{self.project_id}/user",
                f"{self.host}/v0/projects/{self.project_id}/users/me",
            ]
        else:
            endpoints = [
                f"{self.host}/api/v3/user",
                f"{self.host}/api/v3/users/me",
            ]

        for endpoint in endpoints:
            email = self._email_from_endpoint(endpoint, pat)
            if email:
                return email
        return None

    def _email_from_endpoint(self, endpoint: str, pat: str) -> Optional[str]:
        try:
            response = requests.get(endpoint, headers=self._headers(pat), timeout=10)
            if response.status_code >= 400:
                return None
            payload = response.json()
        except Exception:
            return None
        return extract_email(payload)

    def _email_from_pat_payload(self, pat: str) -> Optional[str]:
        # Alguns tokens são JWT. Dremio PAT pode ser opaco em certos ambientes;
        # nesse caso esta estratégia simplesmente retorna None.
        try:
            parts = pat.split(".")
            if len(parts) < 2:
                return None
            payload_segment = parts[1] + "=" * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_segment.encode("utf-8")))
        except Exception:
            return None
        return extract_email(payload)

    def _email_from_current_user_sql(self, engine: DremioEngine) -> Optional[str]:
        for sql in ("SELECT CURRENT_USER AS user_email", "SELECT USER AS user_email"):
            try:
                result = engine.run_sql(sql)
                if result.rows and result.rows[0]:
                    return str(result.rows[0][0])
            except Exception:
                continue
        return None


def normalize_email(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    email = str(value).strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        return None
    return email


def build_user_id(email: str) -> str:
    normalized = normalize_email(email)
    if not normalized:
        raise ValueError("E-mail inválido para geração de user_id.")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_email(payload: Any) -> Optional[str]:
    if isinstance(payload, str):
        return payload if "@" in payload else None

    if isinstance(payload, list):
        for item in payload:
            email = extract_email(item)
            if email:
                return email
        return None

    if not isinstance(payload, dict):
        return None

    direct_keys = (
        "email",
        "userEmail",
        "user_email",
        "username",
        "userName",
        "name",
        "preferred_username",
        "sub",
    )
    for key in direct_keys:
        value = payload.get(key)
        if isinstance(value, str) and "@" in value:
            return value

    nested_keys = ("user", "profile", "data", "principal", "owner")
    for key in nested_keys:
        email = extract_email(payload.get(key))
        if email:
            return email

    return None
