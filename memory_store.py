import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from google.cloud import firestore
except Exception:  # pragma: no cover - permite rodar local sem Firestore instalado/configurado
    firestore = None


class MemoryStoreUnavailable(RuntimeError):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FirestoreMemoryStore:
    """Persistência operacional de conversas.

    Firestore guarda identidade, mensagens e metadados. Resultado pesado continua
    fora daqui: GCS/cache/engine. Nada de DataFrame gigante no banco — sem lixão
    gourmet com carimbo serverless.
    """

    def __init__(self, project_id: Optional[str] = None, prefix: Optional[str] = None):
        if firestore is None:
            raise MemoryStoreUnavailable("google-cloud-firestore não está instalado.")
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.prefix = (prefix or os.getenv("FIRESTORE_COLLECTION_PREFIX", "")).strip()
        self.client = firestore.Client(project=self.project_id) if self.project_id else firestore.Client()

    def _collection(self, name: str):
        return self.client.collection(f"{self.prefix}{name}")

    def upsert_user(self, user_id: str, email: str) -> None:
        ref = self._collection("users").document(user_id)
        snapshot = ref.get()
        payload = {
            "email": email,
            "provider": "dremio_pat",
            "status": "active",
            "last_login_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        if not snapshot.exists:
            payload["created_at"] = firestore.SERVER_TIMESTAMP
        ref.set(payload, merge=True)

    def create_conversation(
        self,
        user_id: str,
        title: str = "Nova conversa",
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        conversation_id = str(uuid.uuid4())
        payload = {
            "id": conversation_id,
            "user_id": user_id,
            "title": title,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "active_sources": [],
            "selected_dremio_view": None,
            "uploaded_files_gcs": [],
            "last_query_sql": None,
            "last_result_ref": None,
            "last_result_summary": None,
            "saved": True,
            "status": "active",
        }
        if metadata:
            payload.update(metadata)
        self._collection("conversations").document(conversation_id).set(payload)
        return conversation_id

    def update_conversation(self, conversation_id: str, **fields: Any) -> None:
        if not conversation_id:
            return
        clean_fields = {key: value for key, value in fields.items() if value is not None}
        clean_fields["updated_at"] = firestore.SERVER_TIMESTAMP
        self._collection("conversations").document(conversation_id).set(clean_fields, merge=True)

    def list_conversations(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        query = self._collection("conversations").where("user_id", "==", user_id).limit(max(limit, 1) * 3)
        docs = [doc.to_dict() for doc in query.stream()]
        docs = [doc for doc in docs if doc.get("status") != "deleted"]
        docs.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
        return docs[:limit]

    def get_conversation(self, conversation_id: str) -> Optional[dict[str, Any]]:
        snapshot = self._collection("conversations").document(conversation_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        **metadata: Any,
    ) -> str:
        if not conversation_id:
            raise ValueError("conversation_id é obrigatório para salvar mensagem.")
        message_id = str(uuid.uuid4())
        payload = {
            "id": message_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "created_at_iso": utc_now_iso(),
        }
        payload.update({key: value for key, value in metadata.items() if value is not None})
        self._collection("conversations").document(conversation_id).collection("messages").document(message_id).set(payload)
        self.update_conversation(conversation_id)
        return message_id

    def get_messages(self, conversation_id: str, limit: int = 50) -> list[dict[str, Any]]:
        docs = [
            doc.to_dict()
            for doc in self._collection("conversations")
            .document(conversation_id)
            .collection("messages")
            .limit(max(limit, 1) * 3)
            .stream()
        ]
        docs.sort(key=lambda item: str(item.get("created_at_iso") or item.get("timestamp") or ""))
        return docs[-limit:]


def get_memory_store() -> Optional[FirestoreMemoryStore]:
    backend = os.getenv("MEMORY_BACKEND", "firestore").strip().lower()
    if backend in ("", "none", "disabled", "off"):
        return None
    if backend != "firestore":
        raise MemoryStoreUnavailable(f"MEMORY_BACKEND não suportado: {backend}")
    try:
        return FirestoreMemoryStore()
    except Exception as exc:
        raise MemoryStoreUnavailable(str(exc)) from exc
