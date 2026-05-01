import os
import tempfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from agent import Agent
from auth import DremioPATAuthenticator
from dremio_engine import DremioEngine
from gcs_upload import create_signed_upload_url, get_gcs_hmac_credentials, get_upload_bucket
from hybrid_engine import HybridEngine
from memory_store import MemoryStoreUnavailable, get_memory_store
from spreadsheet_engine import SpreadsheetEngine


DREMIO_CLOUD_HOST = os.getenv("DREMIO_HOST", "https://api.dremio.cloud").strip()
DREMIO_CLOUD_PROJECT_ID = os.getenv(
    "DREMIO_PROJECT_ID",
    "e2f7d480-9c76-49c0-86e5-18555dd15571",
).strip()

st.set_page_config(page_title="Fin BigData", page_icon="📊", layout="wide")


def init_state():
    defaults = {
        "engine": None,
        "agent": None,
        "messages": [],
        "loaded_files": [],
        "signed_upload": None,
        "dremio_engine": None,
        "spreadsheet_engine": None,
        "dremio_loaded_files": [],
        "spreadsheet_loaded_files": [],
        "dremio_catalogs": [],
        "dremio_containers": [],
        "dremio_views": [],
        "dremio_selected_catalog": None,
        "dremio_selected_container": None,
        "dremio_selected_view": None,
        "authenticated": False,
        "user_email": None,
        "user_id": None,
        "dremio_pat": None,
        "memory_store": None,
        "memory_error": None,
        "conversation_id": None,
        "saved_conversations": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_vertex_config():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    return project_id, location, model


def memory():
    if st.session_state.get("memory_store") or st.session_state.get("memory_error"):
        return st.session_state.get("memory_store")
    try:
        st.session_state.memory_store = get_memory_store()
    except MemoryStoreUnavailable as exc:
        st.session_state.memory_error = str(exc)
        st.session_state.memory_store = None
    return st.session_state.get("memory_store")


def refresh_conversations():
    store = memory()
    user_id = st.session_state.get("user_id")
    if store and user_id:
        st.session_state.saved_conversations = store.list_conversations(user_id)
    else:
        st.session_state.saved_conversations = []


def ensure_conversation(title: str = "Nova conversa") -> str | None:
    if st.session_state.get("conversation_id"):
        return st.session_state.conversation_id
    store = memory()
    user_id = st.session_state.get("user_id")
    if not store or not user_id:
        return None
    conversation_id = store.create_conversation(user_id=user_id, title=title)
    st.session_state.conversation_id = conversation_id
    refresh_conversations()
    return conversation_id


def append_persistent_message(role: str, content: str, **metadata):
    conversation_id = ensure_conversation(title=(content[:48] if role == "user" else "Nova conversa"))
    store = memory()
    if store and conversation_id:
        store.append_message(conversation_id, role, content, **metadata)


def update_conversation_state(**metadata):
    store = memory()
    conversation_id = st.session_state.get("conversation_id")
    if store and conversation_id:
        store.update_conversation(conversation_id, **metadata)
        refresh_conversations()


def load_conversation(conversation_id: str):
    store = memory()
    if not store:
        return
    messages = store.get_messages(conversation_id, limit=50)
    st.session_state.conversation_id = conversation_id
    st.session_state.messages = [
        {"role": m.get("role"), "content": m.get("content", "")}
        for m in messages
        if m.get("role") in ("user", "assistant")
    ]
    if st.session_state.get("agent"):
        st.session_state.agent.load_history(st.session_state.messages)


def create_agent(engine):
    project_id, location, model = get_vertex_config()
    if not project_id:
        st.error("Defina GOOGLE_CLOUD_PROJECT no ambiente antes de iniciar o agente.")
        return None
    agent = Agent(engine, model=model, project_id=project_id, location=location)
    if st.session_state.get("messages"):
        agent.load_history(st.session_state.messages)
    return agent


def activate_engine(engine, loaded: list[str], success_message: str, source_metadata: dict | None = None):
    agent = create_agent(engine)
    if agent:
        st.session_state.engine = engine
        st.session_state.agent = agent
        st.session_state.loaded_files = loaded
        ensure_conversation()
        metadata = dict(source_metadata or {})
        metadata.setdefault("active_sources", loaded)
        update_conversation_state(**metadata)
        st.success(success_message)


def configure_engine_gcs(engine: SpreadsheetEngine):
    hmac_id, hmac_secret = get_gcs_hmac_credentials()
    if hmac_id and hmac_secret:
        engine.configure_gcs(hmac_id, hmac_secret)
    else:
        engine.configure_gcs()


def save_uploaded_file(uploaded_file) -> str:
    tmp_dir = Path(tempfile.gettempdir()) / "fin-bigdata-upload"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    target = tmp_dir / uploaded_file.name
    target.write_bytes(uploaded_file.getbuffer())
    return str(target)


def result_summary(result) -> str | None:
    if not result:
        return None
    return f"{result.row_count} linhas, {len(result.columns)} colunas, {result.execution_time_ms}ms"


def render_download_buttons():
    agent = st.session_state.get("agent")
    if not agent:
        return
    result = getattr(agent, "last_query_result", None)
    if not result or not result.rows:
        return

    df = pd.DataFrame(result.rows, columns=result.columns)
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="resultado")

    unique_key = f"{len(st.session_state.messages)}_{result.row_count}_{abs(hash(result.sql_executed or ''))}"
    st.divider()
    st.caption(f"Resultado disponível para download: {len(df):,} linhas")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Baixar CSV", csv_bytes, "resultado_fin_bigdata.csv", "text/csv", use_container_width=True, key=f"download_csv_{unique_key}")
    with col2:
        st.download_button("Baixar Excel", excel_buffer.getvalue(), "resultado_fin_bigdata.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True, key=f"download_excel_{unique_key}")


def start_spreadsheet_agent(engine: SpreadsheetEngine, loaded: list[str], gcs_uri: str | None = None):
    st.session_state.spreadsheet_engine = engine
    st.session_state.spreadsheet_loaded_files = loaded
    activate_engine(
        engine,
        loaded,
        "Planilha carregada e agente inicializado.",
        {"uploaded_files_gcs": [gcs_uri] if gcs_uri else []},
    )


def setup_local_spreadsheet_upload():
    st.markdown("#### Upload local")
    st.caption("Indicado para arquivos pequenos. Em Cloud Run, prefira o upload via GCS para evitar limite de request.")
    uploads = st.file_uploader("Arquivos", type=["csv", "xlsx", "xls", "parquet"], accept_multiple_files=True)
    if st.button("Carregar arquivos locais", type="primary", disabled=not uploads):
        engine = SpreadsheetEngine()
        loaded = []
        for uploaded in uploads:
            path = save_uploaded_file(uploaded)
            table_name = Path(uploaded.name).stem.lower().replace("-", "_").replace(" ", "_")
            try:
                table = engine.load_file(path, table_name)
                info = engine.describe_table(table)
                loaded.append(f"{info.full_path} — {info.row_count:,} linhas")
            except Exception as exc:
                st.error(f"Erro ao carregar {uploaded.name}: {exc}")
                return
        start_spreadsheet_agent(engine, loaded)


def render_signed_upload_component(signed_url: str, gcs_uri: str):
    components.html(
        f"""
        <div style='border:1px solid rgba(250,250,250,.28);border-radius:12px;padding:14px;font-family:Inter;color:#f8fafc;background:rgba(255,255,255,.04)'>
          <b>Upload direto para GCS</b><br/><br/>
          <input id='file' type='file' style='width:100%;margin-bottom:10px;color:#f8fafc'/>
          <button id='upload' style='width:100%;border:0;border-radius:10px;background:#ff4b4b;color:white;padding:9px;font-weight:700'>Enviar para GCS</button>
          <pre id='status' style='white-space:pre-wrap;background:rgba(15,23,42,.9);padding:10px;border-radius:10px'>Selecione o arquivo e envie para o bucket.</pre>
        </div>
        <script>
        const signedUrl = {signed_url!r};
        const gcsUri = {gcs_uri!r};
        document.getElementById('upload').onclick = async () => {{
          const file = document.getElementById('file').files[0];
          const status = document.getElementById('status');
          if (!file) {{ status.textContent = 'Selecione um arquivo primeiro.'; return; }}
          status.textContent = 'Enviando...';
          try {{
            const response = await fetch(signedUrl, {{ method: 'PUT', body: file }});
            const detail = await response.text();
            if (!response.ok) throw new Error(`HTTP ${{response.status}} ${{detail}}`);
            status.textContent = `Upload concluído. Agora clique em "Usar arquivo enviado" no app.\n${{gcsUri}}`;
          }} catch (err) {{ status.textContent = `Falha no upload: ${{err.message}}`; }}
        }};
        </script>
        """,
        height=220,
    )


def setup_gcs_spreadsheet_upload():
    st.markdown("#### Upload grande via GCS")
    st.caption("O arquivo vai direto do navegador para o bucket. O Streamlit recebe só o caminho gs:// para consulta.")
    try:
        bucket = get_upload_bucket()
        st.caption(f"Bucket configurado: `{bucket}`")
    except Exception as exc:
        st.warning(f"Upload via GCS indisponível: {exc}")
        return

    filename = st.text_input("Nome do arquivo", placeholder="base_cobranca.xlsx, base_cobranca.csv ou base_cobranca.parquet")
    if st.button("Gerar signed URL", disabled=not filename):
        try:
            st.session_state.signed_upload = create_signed_upload_url(filename=filename)
        except Exception as exc:
            st.error(f"Falha ao gerar signed URL: {exc}")

    signed_upload = st.session_state.get("signed_upload")
    if signed_upload:
        st.code(signed_upload.gcs_uri)
        render_signed_upload_component(signed_upload.signed_url, signed_upload.gcs_uri)
        table_name = Path(signed_upload.object_name).stem.lower().replace("-", "_").replace(" ", "_")
        table_name = st.text_input("Nome da tabela no DuckDB", value=table_name)
        if st.button("Usar arquivo enviado", type="primary"):
            engine = SpreadsheetEngine()
            try:
                configure_engine_gcs(engine)
                table = engine.load_file(signed_upload.gcs_uri, table_name)
                info = engine.describe_table(table)
                start_spreadsheet_agent(engine, [f"{info.full_path} — {info.row_count:,} linhas — {signed_upload.gcs_uri}"], signed_upload.gcs_uri)
            except Exception as exc:
                st.error(f"Erro ao carregar arquivo do GCS: {exc}")


def setup_spreadsheet_ui():
    st.subheader("Fonte Planilha")
    st.caption("Use DuckDB para consultar CSV, XLSX ou Parquet. Para arquivos grandes, use GCS.")
    tab_gcs, tab_local = st.tabs(["GCS / arquivo grande", "Upload local / dev"])
    with tab_gcs:
        setup_gcs_spreadsheet_upload()
    with tab_local:
        setup_local_spreadsheet_upload()


def _create_dremio_engine(pat: str) -> DremioEngine:
    return DremioEngine(DREMIO_CLOUD_HOST, pat, DREMIO_CLOUD_PROJECT_ID, is_cloud=True, allowed_paths=[])


def _display_path_tail(path: str, levels: int = 1) -> str:
    parts = [p.strip().strip('"').strip("'") for p in path.split(".") if p.strip()]
    return " / ".join(parts[-levels:]) if parts else path


def _unique_display_map(values: list[str], levels: int = 1) -> dict[str, str]:
    labels = [_display_path_tail(value, levels=levels) for value in values]
    duplicated = {label for label in labels if labels.count(label) > 1}
    return {(_display_path_tail(value, levels=2) if label in duplicated else label): value for value, label in zip(values, labels)}


def _view_label(view) -> str:
    return getattr(view, "name", None) or _display_path_tail(view.full_path, levels=1)


def _unique_view_display_map(views) -> dict[str, object]:
    labels = [_view_label(view) for view in views]
    duplicated = {label for label in labels if labels.count(label) > 1}
    return {(_display_path_tail(view.full_path, levels=2) if label in duplicated else label): view for view, label in zip(views, labels)}


def setup_dremio_ui():
    st.subheader("Fonte Dremio")
    st.caption("Escolha catálogo, pasta e view com o PAT validado no desbloqueio do app.")
    effective_pat = st.session_state.get("dremio_pat")
    if not effective_pat:
        st.info("Desbloqueie o app com seu PAT do Dremio para carregar as fontes.")
        return

    st.caption(f"Usuário Dremio: `{st.session_state.get('user_email')}`")
    if st.button("Buscar catálogos"):
        try:
            engine = _create_dremio_engine(effective_pat)
            st.session_state.dremio_catalogs = engine.list_catalogs()
            st.session_state.dremio_containers = []
            st.session_state.dremio_views = []
            st.session_state.dremio_selected_catalog = None
            st.session_state.dremio_selected_container = None
            st.session_state.dremio_selected_view = None
            if not st.session_state.dremio_catalogs:
                st.warning("Nenhum catálogo visível para este PAT.")
        except Exception as exc:
            st.error(f"Falha ao buscar catálogos: {exc}")

    catalogs = st.session_state.get("dremio_catalogs", [])
    selected_catalog = None
    if catalogs:
        selected_catalog = st.selectbox("Catálogo/Workspace", catalogs, key="dremio_catalog_select")
        if selected_catalog != st.session_state.get("dremio_selected_catalog"):
            st.session_state.dremio_selected_catalog = selected_catalog
            st.session_state.dremio_containers = []
            st.session_state.dremio_views = []
            st.session_state.dremio_selected_container = None
            st.session_state.dremio_selected_view = None
        if st.button("Listar pastas", disabled=not selected_catalog):
            try:
                engine = _create_dremio_engine(effective_pat)
                st.session_state.dremio_containers = engine.list_child_containers(selected_catalog)
                st.session_state.dremio_views = []
                if not st.session_state.dremio_containers:
                    st.warning("Não encontrei pastas nesse catálogo.")
            except Exception as exc:
                st.error(f"Falha ao listar pastas: {exc}")

    containers = st.session_state.get("dremio_containers", [])
    selected_container = None
    if containers:
        container_map = _unique_display_map(containers, levels=1)
        container_options = ["(usar catálogo inteiro)"] + list(container_map.keys())
        selected_container_label = st.selectbox("Pasta", container_options, key="dremio_container_select")
        selected_container = selected_catalog if selected_container_label == "(usar catálogo inteiro)" else container_map[selected_container_label]
        if selected_container != st.session_state.get("dremio_selected_container"):
            st.session_state.dremio_selected_container = selected_container
            st.session_state.dremio_views = []
            st.session_state.dremio_selected_view = None
        if st.button("Carregar views da pasta", disabled=not selected_container):
            try:
                engine = _create_dremio_engine(effective_pat)
                st.session_state.dremio_views = engine.list_datasets(selected_container, recursive=True)
                st.session_state.dremio_selected_view = None
                if not st.session_state.dremio_views:
                    st.warning("Não encontrei views nessa pasta.")
            except Exception as exc:
                st.error(f"Falha ao carregar views: {exc}")

    views = st.session_state.get("dremio_views", [])
    selected_view = None
    if views:
        view_search = st.text_input("View", value="", placeholder="Digite o nome da view. Ex: INAD", key="dremio_view_search")
        query = view_search.strip().lower()
        filtered_views = [view for view in views if not query or query in _view_label(view).lower() or query in view.full_path.lower()]
        if filtered_views:
            view_map = _unique_view_display_map(filtered_views)
            selected_view_label = st.selectbox("Views encontradas", list(view_map.keys()), key="dremio_view_select")
            selected_view_obj = view_map[selected_view_label]
            selected_view = selected_view_obj.full_path
            st.session_state.dremio_selected_view = selected_view
            st.caption(f"View selecionada: `{_view_label(selected_view_obj)}`")
            st.caption(f"Caminho técnico: `{selected_view}`")
        else:
            st.info("Nenhuma view encontrada com esse filtro.")
        st.caption(f"{len(filtered_views)} de {len(views)} view(s) encontrada(s).")

    if st.button("Conectar Dremio", type="primary", disabled=not (selected_catalog or selected_view)):
        try:
            if selected_view:
                allowed = [selected_view]
                loaded_label = f"View selecionada: {_display_path_tail(selected_view, levels=1)}"
            elif views:
                allowed = [view.full_path for view in views]
                loaded_label = f"{len(views)} views selecionadas"
            else:
                path = st.session_state.get("dremio_selected_container") or selected_catalog
                allowed = [path] if path else []
                loaded_label = f"Catálogo selecionado: {path}"
            engine = DremioEngine(DREMIO_CLOUD_HOST, effective_pat, DREMIO_CLOUD_PROJECT_ID, is_cloud=True, allowed_paths=allowed)
            tables = engine.list_tables()
            loaded = [loaded_label, f"{len(tables)} tabelas/views visíveis no Dremio"]
            st.session_state.dremio_engine = engine
            st.session_state.dremio_loaded_files = loaded
            activate_engine(engine, loaded, "Dremio conectado e agente inicializado.", {"selected_dremio_view": selected_view})
        except Exception as exc:
            st.error(f"Falha ao conectar no Dremio: {exc}")


def render_relationship_ui():
    st.markdown("### Relacionamento")
    st.caption("Combine Dremio e Planilha para cruzar dados entre fontes no chat.")
    has_dremio = st.session_state.get("dremio_engine") is not None
    has_spreadsheet = st.session_state.get("spreadsheet_engine") is not None
    if not has_dremio or not has_spreadsheet:
        st.button("🔗 Criar relacionamento entre fontes", disabled=True, use_container_width=True)
        missing = []
        if not has_dremio:
            missing.append("Dremio")
        if not has_spreadsheet:
            missing.append("Planilha")
        st.caption(f"Conecte {' e '.join(missing)} para ativar a análise combinada.")
        return
    if st.button("🔗 Ativar análise combinada", type="primary", use_container_width=True):
        hybrid = HybridEngine(st.session_state.dremio_engine, st.session_state.spreadsheet_engine)
        loaded = ["Modo combinado ativo: Dremio + Planilha", *st.session_state.get("dremio_loaded_files", []), *st.session_state.get("spreadsheet_loaded_files", [])]
        activate_engine(hybrid, loaded, "Análise combinada ativada. Oriente o agente pelo chat sobre como relacionar as fontes.")
    st.caption("Exemplo: busque um contrato no Dremio; com nome/CPF encontrados, procure o cliente na planilha.")


def reset_workspace(keep_auth: bool = True):
    preserved = {}
    if keep_auth:
        for key in ["authenticated", "user_email", "user_id", "dremio_pat", "memory_store", "memory_error", "conversation_id", "saved_conversations"]:
            preserved[key] = st.session_state.get(key)
    for key in [
        "engine", "agent", "messages", "loaded_files", "signed_upload", "dremio_engine", "spreadsheet_engine",
        "dremio_loaded_files", "spreadsheet_loaded_files", "dremio_catalogs", "dremio_containers", "dremio_views",
        "dremio_selected_catalog", "dremio_selected_container", "dremio_selected_view",
    ]:
        st.session_state.pop(key, None)
    if not keep_auth:
        for key in ["authenticated", "user_email", "user_id", "dremio_pat", "memory_store", "memory_error", "conversation_id", "saved_conversations"]:
            st.session_state.pop(key, None)
    init_state()
    for key, value in preserved.items():
        st.session_state[key] = value


def new_conversation():
    st.session_state.conversation_id = None
    st.session_state.messages = []
    if st.session_state.get("agent"):
        st.session_state.agent.load_history([])
    ensure_conversation()
    st.rerun()


def render_conversation_sidebar():
    st.markdown("### Conversas")
    st.caption("Abra uma conversa salva depois de conectar uma fonte, ou comece uma nova análise.")
    if st.session_state.get("memory_error"):
        st.caption(f"Memória persistente indisponível: {st.session_state.memory_error}")
        return
    if not memory():
        st.caption("Memória persistente desativada.")
        return
    if st.button("Nova conversa", use_container_width=True):
        new_conversation()
    refresh_conversations()
    conversations = st.session_state.get("saved_conversations", [])
    if not conversations:
        st.caption("Nenhuma conversa salva ainda.")
        return
    labels = []
    id_by_label = {}
    for conv in conversations:
        title = conv.get("title") or "Conversa sem título"
        suffix = conv.get("id", "")[:8]
        label = f"{title[:42]} · {suffix}"
        labels.append(label)
        id_by_label[label] = conv.get("id")
    current = st.session_state.get("conversation_id")
    current_label = next((label for label, cid in id_by_label.items() if cid == current), labels[0])
    selected = st.selectbox("Abrir conversa", labels, index=labels.index(current_label), key="conversation_select")
    if id_by_label[selected] != current:
        load_conversation(id_by_label[selected])
        st.rerun()


def render_sidebar():
    _, _, model = get_vertex_config()
    with st.sidebar:
        st.title("Fin BigData")
        st.caption("Análises de BigData")
        st.markdown("### Agente")
        st.write(f"Modelo: `{model}`")
        if st.session_state.get("authenticated"):
            st.success("App desbloqueado")
            st.caption(f"Usuário: `{st.session_state.get('user_email')}`")
            if st.button("Trocar PAT / sair"):
                reset_workspace(keep_auth=False)
                st.rerun()
        else:
            st.warning("App bloqueado. Informe seu PAT para liberar o agente.")
        st.divider()
        setup_dremio_ui()
        st.divider()
        setup_spreadsheet_ui()
        st.divider()
        render_relationship_ui()
        st.divider()
        st.markdown("### Estado")
        if st.session_state.engine:
            st.success(st.session_state.engine.engine_name)
            for item in st.session_state.loaded_files:
                st.caption(item)
        else:
            st.warning("Nenhuma engine ativa.")
        if st.button("Resetar sessão"):
            reset_workspace(keep_auth=True)
            st.rerun()
        if st.session_state.get("authenticated"):
            st.divider()
            render_conversation_sidebar()


def render_auth_gate() -> bool:
    if st.session_state.get("authenticated"):
        return True
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"] { filter: blur(1.5px); opacity: 0.72; }
          .auth-card { max-width:560px;margin:8vh auto 0 auto;padding:28px;border:1px solid rgba(250,250,250,.16);border-radius:22px;background:rgba(17,24,39,.78);box-shadow:0 24px 80px rgba(0,0,0,.35); }
          .auth-title { font-size:32px;font-weight:800;margin-bottom:6px; }
          .auth-subtitle { opacity:.76;margin-bottom:18px; }
        </style>
        <div class="auth-card"><div class="auth-title">Desbloquear Fin BigData</div><div class="auth-subtitle">Use seu PAT do Dremio para validar permissões e identificar seu e-mail corporativo. O token fica somente em memória nesta sessão.</div></div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("dremio_pat_unlock_form"):
        pat = st.text_input("Personal Access Token do Dremio", value="", type="password", placeholder="Cole aqui o seu PAT do Dremio")
        submitted = st.form_submit_button("Desbloquear app", type="primary", use_container_width=True)
    if submitted:
        try:
            authenticator = DremioPATAuthenticator(DREMIO_CLOUD_HOST, DREMIO_CLOUD_PROJECT_ID, is_cloud=True)
            user = authenticator.authenticate(pat)
            st.session_state.authenticated = True
            st.session_state.user_email = user.email
            st.session_state.user_id = user.user_id
            st.session_state.dremio_pat = pat.strip()
            store = memory()
            if store:
                store.upsert_user(user.user_id, user.email)
                refresh_conversations()
            st.success(f"App desbloqueado para {user.email}.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não consegui validar o PAT no Dremio: {exc}")
    st.info("Depois de desbloquear, escolha a fonte Dremio ou Planilha na barra lateral para iniciar o agente.")
    return False


def render_chat():
    st.title("📊 Fin BigData")
    st.caption("Bancada analítica assistida por Gemini. O agente consulta dados estruturados, não arquivo bruto no prompt.")
    if st.session_state.get("conversation_id"):
        st.caption(f"Conversa: `{st.session_state.conversation_id}`")
    if not st.session_state.agent:
        st.info("Escolha uma fonte de dados na barra lateral para iniciar o agente.")
        return

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Pergunte algo sobre os dados...")
    if not user_input:
        render_download_buttons()
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    append_persistent_message("user", user_input)
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        status_box = st.empty()
        def update_status(message: str):
            status_box.caption(message)
        update_status("🚀 Iniciando análise")
        try:
            response = st.session_state.agent.chat(user_input, progress_callback=update_status)
        except Exception as exc:
            response = f"Erro ao processar pergunta: {exc}"
            update_status("❌ Erro ao processar pergunta")
        status_box.empty()
        st.markdown(response)
        render_download_buttons()

    result = getattr(st.session_state.agent, "last_query_result", None)
    st.session_state.messages.append({"role": "assistant", "content": response})
    append_persistent_message(
        "assistant",
        response,
        sql=getattr(result, "sql_executed", None),
        query_result_summary=result_summary(result),
    )
    if result:
        update_conversation_state(
            last_query_sql=result.sql_executed,
            last_result_summary=result_summary(result),
        )


def main():
    init_state()
    render_sidebar()
    if not render_auth_gate():
        return
    render_chat()


if __name__ == "__main__":
    main()
