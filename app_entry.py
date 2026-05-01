import streamlit as st
import streamlit.components.v1 as components

import app as base_app
from auth import DremioPATAuthenticator
from dremio_engine import DremioEngine

APP_NAME = "BigDados"
APP_CAPTION = "Bancada analítica para BigDados assistida por Agente Gemini"
NO_SOURCE_MESSAGE = "Escolha suas fontes de dados para iniciar ou continuar uma conversa"


def set_browser_title():
    components.html(
        f"<script>window.parent.document.title = {APP_NAME!r};</script>",
        height=0,
    )


def inject_sidebar_compact_css():
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            padding-top: 1.15rem;
          }
          [data-testid="stSidebar"] h1 {
            margin-top: 0 !important;
            padding-top: 0 !important;
          }
          [data-testid="stSidebar"] .block-container {
            padding-top: 1rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def phase_state():
    if "active_dremio_sources" not in st.session_state:
        st.session_state.active_dremio_sources = []
    if "source_relationships" not in st.session_state:
        st.session_state.source_relationships = []
    if "source_columns_by_path" not in st.session_state:
        st.session_state.source_columns_by_path = {}
    if "show_source_manager" not in st.session_state:
        st.session_state.show_source_manager = False


def first_name_from_email(email: str | None) -> str:
    if not email or "@" not in email:
        return ""
    first = email.split("@", 1)[0].split(".", 1)[0].strip()
    return first[:1].upper() + first[1:].lower() if first else ""


def home_title() -> str:
    first_name = first_name_from_email(st.session_state.get("user_email"))
    if first_name:
        return f"Olá, {first_name}, o que vamos analisar agora?"
    return "Olá, o que vamos analisar agora?"


def source_name_from_path(path: str) -> str:
    return base_app._display_path_tail(path, levels=1)


def source_alias_from_name(name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in name)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "fonte"


def find_source(path: str) -> dict | None:
    for source in st.session_state.get("active_dremio_sources", []):
        if source.get("path") == path:
            return source
    return None


def add_dremio_source(path: str, name: str | None = None):
    phase_state()
    name = name or source_name_from_path(path)
    current = st.session_state.active_dremio_sources
    if any(src.get("path") == path for src in current):
        st.info(f"{name} já está na lista de fontes.")
        return
    current.append({
        "type": "dremio_view",
        "path": path,
        "name": name,
        "alias": source_alias_from_name(name),
    })
    st.session_state.active_dremio_sources = current
    st.success(f"Adicionei {name} às fontes da análise.")


def remove_dremio_source(path: str):
    st.session_state.active_dremio_sources = [
        src for src in st.session_state.get("active_dremio_sources", [])
        if src.get("path") != path
    ]
    st.session_state.source_relationships = [
        rel for rel in st.session_state.get("source_relationships", [])
        if rel.get("left_path") != path and rel.get("right_path") != path
    ]
    persist_relationships()


def relationship_label(rel: dict) -> str:
    return (
        f"{rel.get('left_name')}.{rel.get('left_column')} "
        f"= {rel.get('right_name')}.{rel.get('right_column')}"
    )


def build_agent_context() -> str:
    sources = st.session_state.get("active_dremio_sources", [])
    relationships = st.session_state.get("source_relationships", [])
    if not sources and not relationships:
        return ""

    lines = [
        "\n\nCONTEXTO DO WORKSPACE BIGDADOS:",
        "As fontes abaixo foram selecionadas pelo usuário para esta conversa.",
    ]
    if sources:
        lines.append("\nFontes ativas:")
        for src in sources:
            lines.append(f"- alias `{src.get('alias')}` | nome `{src.get('name')}` | path {src.get('path')}")

    if relationships:
        lines.append("\nRelacionamentos conhecidos definidos pelo usuário:")
        for rel in relationships:
            lines.append(
                f"- `{rel.get('left_name')}`.`{rel.get('left_column')}` "
                f"= `{rel.get('right_name')}`.`{rel.get('right_column')}` "
                f"(confiança: {rel.get('confidence', 'manual')})"
            )
        lines.append(
            "\nQuando o usuário pedir análise cruzada entre fontes, use esses relacionamentos "
            "como chaves preferenciais. Ainda assim, descreva e amostre as tabelas antes de montar SQL. "
            "Se a junção puder duplicar linhas, avise e prefira validar contagens/amostras antes de concluir."
        )
    return "\n".join(lines)


def apply_agent_workspace_context():
    agent = st.session_state.get("agent")
    if not agent:
        return
    if not hasattr(agent, "base_system"):
        agent.base_system = agent.system
    agent.system = agent.base_system + build_agent_context()


def persist_relationships():
    relationships = st.session_state.get("source_relationships", [])
    base_app.update_conversation_state(relationships=relationships)
    apply_agent_workspace_context()


def get_dremio_engine_for_metadata() -> DremioEngine | None:
    pat = st.session_state.get("dremio_pat")
    if not pat:
        return None
    engine = st.session_state.get("dremio_engine")
    if engine:
        return engine
    paths = [src["path"] for src in st.session_state.get("active_dremio_sources", [])]
    return DremioEngine(
        base_app.DREMIO_CLOUD_HOST,
        pat,
        base_app.DREMIO_CLOUD_PROJECT_ID,
        is_cloud=True,
        allowed_paths=paths,
    )


def load_columns_for_source(path: str) -> list[str]:
    phase_state()
    cache = st.session_state.source_columns_by_path
    if path in cache:
        return cache[path]
    engine = get_dremio_engine_for_metadata()
    if not engine:
        return []
    info = engine.describe_table(path)
    columns = [col.get("name") for col in info.columns if col.get("name")]
    cache[path] = columns
    st.session_state.source_columns_by_path = cache
    return columns


def load_all_source_columns():
    for source in st.session_state.get("active_dremio_sources", []):
        load_columns_for_source(source["path"])


def add_relationship(left_path: str, left_column: str, right_path: str, right_column: str):
    if not left_path or not right_path or left_path == right_path:
        st.warning("Escolha duas fontes diferentes para criar o relacionamento.")
        return
    if not left_column or not right_column:
        st.warning("Escolha as colunas dos dois lados do relacionamento.")
        return

    left = find_source(left_path)
    right = find_source(right_path)
    if not left or not right:
        st.error("Não encontrei uma das fontes selecionadas.")
        return

    relationship = {
        "left_path": left_path,
        "left_name": left["name"],
        "left_alias": left["alias"],
        "left_column": left_column,
        "right_path": right_path,
        "right_name": right["name"],
        "right_alias": right["alias"],
        "right_column": right_column,
        "confidence": "manual",
    }
    existing = st.session_state.get("source_relationships", [])
    signature = (left_path, left_column, right_path, right_column)
    reverse_signature = (right_path, right_column, left_path, left_column)
    for rel in existing:
        rel_signature = (rel.get("left_path"), rel.get("left_column"), rel.get("right_path"), rel.get("right_column"))
        if rel_signature in (signature, reverse_signature):
            st.info("Esse relacionamento já existe.")
            return
    existing.append(relationship)
    st.session_state.source_relationships = existing
    persist_relationships()
    st.success(f"Relacionamento criado: {relationship_label(relationship)}")


def remove_relationship(index: int):
    relationships = st.session_state.get("source_relationships", [])
    if 0 <= index < len(relationships):
        relationships.pop(index)
        st.session_state.source_relationships = relationships
        persist_relationships()


def connect_dremio_sources() -> bool:
    phase_state()
    sources = st.session_state.get("active_dremio_sources", [])
    pat = st.session_state.get("dremio_pat")
    if not pat:
        st.error("Desbloqueie o app com seu PAT antes de conectar fontes.")
        return False
    if not sources:
        st.warning("Adicione pelo menos uma view Dremio antes de conectar.")
        return False

    paths = [src["path"] for src in sources]
    engine = DremioEngine(
        base_app.DREMIO_CLOUD_HOST,
        pat,
        base_app.DREMIO_CLOUD_PROJECT_ID,
        is_cloud=True,
        allowed_paths=paths,
    )
    tables = engine.list_tables()
    loaded = [f"Dremio · {len(paths)} view(s) selecionada(s)"] + [f"{src['name']} — {src['path']}" for src in sources]
    st.session_state.dremio_engine = engine
    st.session_state.dremio_loaded_files = loaded
    base_app.activate_engine(
        engine,
        loaded,
        f"Dremio conectado com {len(paths)} view(s).",
        {
            "selected_dremio_view": paths[0] if len(paths) == 1 else None,
            "dremio_sources": sources,
            "relationships": st.session_state.get("source_relationships", []),
            "active_sources": loaded,
        },
    )
    apply_agent_workspace_context()
    if len(tables) != len(paths):
        st.caption(f"Aviso técnico: o engine expôs {len(tables)} tabela(s)/view(s) para {len(paths)} path(s) selecionado(s).")
    return True


def render_dremio_source_picker():
    st.markdown("#### Dremio")
    st.caption("Adicione uma ou mais views ao ambiente analítico desta conversa.")
    effective_pat = st.session_state.get("dremio_pat")
    if not effective_pat:
        st.info("Desbloqueie o app com seu PAT do Dremio para carregar as fontes.")
        return

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Buscar catálogos", use_container_width=True, key="modal_buscar_catalogos"):
            try:
                engine = base_app._create_dremio_engine(effective_pat)
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
    with col_b:
        st.caption(f"Usuário Dremio: `{st.session_state.get('user_email')}`")

    catalogs = st.session_state.get("dremio_catalogs", [])
    selected_catalog = None
    if catalogs:
        selected_catalog = st.selectbox("Catálogo/Workspace", catalogs, key="modal_dremio_catalog_select")
        if selected_catalog != st.session_state.get("dremio_selected_catalog"):
            st.session_state.dremio_selected_catalog = selected_catalog
            st.session_state.dremio_containers = []
            st.session_state.dremio_views = []
            st.session_state.dremio_selected_container = None
            st.session_state.dremio_selected_view = None
        if st.button("Listar pastas", disabled=not selected_catalog, key="modal_listar_pastas"):
            try:
                engine = base_app._create_dremio_engine(effective_pat)
                st.session_state.dremio_containers = engine.list_child_containers(selected_catalog)
                st.session_state.dremio_views = []
                if not st.session_state.dremio_containers:
                    st.warning("Não encontrei pastas nesse catálogo.")
            except Exception as exc:
                st.error(f"Falha ao listar pastas: {exc}")

    containers = st.session_state.get("dremio_containers", [])
    selected_container = None
    if containers:
        container_map = base_app._unique_display_map(containers, levels=1)
        container_options = ["(usar catálogo inteiro)"] + list(container_map.keys())
        selected_container_label = st.selectbox("Pasta", container_options, key="modal_dremio_container_select")
        selected_container = selected_catalog if selected_container_label == "(usar catálogo inteiro)" else container_map[selected_container_label]
        if selected_container != st.session_state.get("dremio_selected_container"):
            st.session_state.dremio_selected_container = selected_container
            st.session_state.dremio_views = []
            st.session_state.dremio_selected_view = None
        if st.button("Carregar views da pasta", disabled=not selected_container, key="modal_carregar_views"):
            try:
                engine = base_app._create_dremio_engine(effective_pat)
                st.session_state.dremio_views = engine.list_datasets(selected_container, recursive=True)
                st.session_state.dremio_selected_view = None
                if not st.session_state.dremio_views:
                    st.warning("Não encontrei views nessa pasta.")
            except Exception as exc:
                st.error(f"Falha ao carregar views: {exc}")

    views = st.session_state.get("dremio_views", [])
    if views:
        view_search = st.text_input("Filtrar view", value="", placeholder="Digite o nome da view. Ex: INAD", key="modal_dremio_view_search")
        query = view_search.strip().lower()
        filtered_views = [view for view in views if not query or query in base_app._view_label(view).lower() or query in view.full_path.lower()]
        if filtered_views:
            view_map = base_app._unique_view_display_map(filtered_views)
            selected_view_label = st.selectbox("Views encontradas", list(view_map.keys()), key="modal_dremio_view_select")
            selected_view_obj = view_map[selected_view_label]
            selected_view = selected_view_obj.full_path
            st.session_state.dremio_selected_view = selected_view
            st.caption(f"Selecionada: `{base_app._view_label(selected_view_obj)}`")
            st.caption(f"Caminho técnico: `{selected_view}`")
            if st.button("Adicionar view à análise", type="secondary", use_container_width=True, key="modal_add_view", disabled=not selected_view):
                add_dremio_source(selected_view, base_app._view_label(selected_view_obj))
        else:
            st.info("Nenhuma view encontrada com esse filtro.")
        st.caption(f"{len(filtered_views)} de {len(views)} view(s) encontrada(s).")


def render_selected_sources():
    phase_state()
    st.markdown("#### Fontes selecionadas")
    sources = st.session_state.get("active_dremio_sources", [])
    if not sources:
        st.caption("Nenhuma view Dremio adicionada ainda.")
        return

    for idx, src in enumerate(sources, start=1):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"**{idx}. {src['name']}**")
            st.caption(src["path"])
        with col2:
            if st.button("Remover", key=f"remove_dremio_source_{idx}"):
                remove_dremio_source(src["path"])
                st.rerun()

    if st.button("Conectar fontes selecionadas", type="primary", use_container_width=True, key="connect_selected_sources"):
        if connect_dremio_sources():
            st.session_state.show_source_manager = False
            st.rerun()


def render_relationship_manager():
    phase_state()
    st.markdown("#### Relacionamentos")
    sources = st.session_state.get("active_dremio_sources", [])
    if len(sources) < 2:
        st.info("Adicione pelo menos duas views Dremio para criar um relacionamento.")
        return

    if st.button("Carregar colunas das fontes", use_container_width=True, key="load_relationship_columns"):
        try:
            load_all_source_columns()
            st.success("Colunas carregadas.")
        except Exception as exc:
            st.error(f"Falha ao carregar colunas: {exc}")

    source_options = {f"{src['name']} · {idx}": src for idx, src in enumerate(sources, start=1)}
    left_label = st.selectbox("Fonte esquerda", list(source_options.keys()), key="relationship_left_source")
    right_label = st.selectbox("Fonte direita", list(source_options.keys()), key="relationship_right_source")
    left = source_options[left_label]
    right = source_options[right_label]

    left_columns = load_columns_for_source(left["path"])
    right_columns = load_columns_for_source(right["path"])

    col1, col2 = st.columns(2)
    with col1:
        left_column = st.selectbox("Coluna esquerda", left_columns or [""], key="relationship_left_column")
    with col2:
        right_column = st.selectbox("Coluna direita", right_columns or [""], key="relationship_right_column")

    if st.button("Criar relacionamento", type="primary", use_container_width=True, key="create_relationship"):
        add_relationship(left["path"], left_column, right["path"], right_column)
        st.rerun()

    st.divider()
    relationships = st.session_state.get("source_relationships", [])
    if not relationships:
        st.caption("Nenhum relacionamento definido ainda.")
        return

    st.markdown("##### Relacionamentos salvos")
    for idx, rel in enumerate(relationships):
        col_a, col_b = st.columns([4, 1])
        with col_a:
            st.markdown(f"**{relationship_label(rel)}**")
            st.caption("Confiança: manual")
        with col_b:
            if st.button("Remover", key=f"remove_relationship_{idx}"):
                remove_relationship(idx)
                st.rerun()


def render_source_manager_content():
    phase_state()
    tab_dremio, tab_planilha, tab_conectadas, tab_relacionamentos = st.tabs([
        "Dremio",
        "Planilha",
        "Fontes conectadas",
        "Relacionamentos",
    ])
    with tab_dremio:
        render_dremio_source_picker()
    with tab_planilha:
        st.caption("Planilhas continuam disponíveis aqui. A multi-view Dremio é o foco desta fase.")
        base_app.setup_spreadsheet_ui()
    with tab_conectadas:
        render_selected_sources()
    with tab_relacionamentos:
        render_relationship_manager()


def open_source_manager():
    if hasattr(st, "dialog"):
        @st.dialog("Gerenciar fontes de dados", width="large")
        def source_dialog():
            render_source_manager_content()
        source_dialog()
    else:
        st.session_state.show_source_manager = not st.session_state.get("show_source_manager", False)


def render_source_summary_sidebar():
    phase_state()
    st.markdown("### Fontes")
    sources = st.session_state.get("active_dremio_sources", [])
    relationships = st.session_state.get("source_relationships", [])
    if sources and st.session_state.get("dremio_engine"):
        st.success(f"Dremio · {len(sources)} view(s)")
        for src in sources[:3]:
            st.caption(src["name"])
        if len(sources) > 3:
            st.caption(f"+ {len(sources) - 3} outra(s)")
        if relationships:
            st.caption(f"Relacionamentos · {len(relationships)}")
    elif st.session_state.get("engine"):
        st.success(st.session_state.engine.engine_name)
        for item in st.session_state.get("loaded_files", [])[:3]:
            st.caption(item)
    else:
        st.warning("Nenhuma fonte ativa.")

    if st.button("Gerenciar fontes", type="primary", use_container_width=True):
        open_source_manager()

    if st.session_state.get("show_source_manager") and not hasattr(st, "dialog"):
        with st.expander("Gerenciar fontes de dados", expanded=True):
            render_source_manager_content()


def hydrate_workspace_from_conversation(conversation_id: str):
    store = base_app.memory()
    if not store or str(conversation_id).startswith("local-"):
        return
    conversation = store.get_conversation(conversation_id)
    if not conversation:
        return
    st.session_state.active_dremio_sources = conversation.get("dremio_sources") or st.session_state.get("active_dremio_sources", [])
    st.session_state.source_relationships = conversation.get("relationships") or []
    st.session_state.pending_source_metadata = {
        **dict(st.session_state.get("pending_source_metadata") or {}),
        "dremio_sources": st.session_state.active_dremio_sources,
        "relationships": st.session_state.source_relationships,
    }
    apply_agent_workspace_context()


def load_conversation_bigdados(conversation_id: str):
    base_app._original_load_conversation(conversation_id)
    hydrate_workspace_from_conversation(conversation_id)


def render_sidebar_bigdados():
    inject_sidebar_compact_css()
    phase_state()
    _, _, model = base_app.get_vertex_config()
    with st.sidebar:
        st.title(APP_NAME)
        st.caption("Análises de BigDados")
        st.caption(f"Modelo: `{model}`")

        if st.session_state.get("authenticated"):
            st.caption(f"Usuário: `{st.session_state.get('user_email')}`")
        else:
            st.warning("App bloqueado. Informe seu PAT para liberar o agente.")

        st.divider()
        render_source_summary_sidebar()

        if st.session_state.get("authenticated"):
            st.divider()
            base_app.render_conversation_sidebar()

        st.divider()
        st.markdown("### Sessão")
        if st.button("Nova análise", use_container_width=True):
            base_app.reset_workspace(keep_auth=True)
            st.session_state.conversation_id = None
            st.session_state.messages = []
            st.session_state.active_dremio_sources = []
            st.session_state.source_relationships = []
            st.session_state.source_columns_by_path = {}
            st.rerun()
        if st.session_state.get("authenticated") and st.button("Trocar PAT / sair", use_container_width=True):
            base_app.reset_workspace(keep_auth=False)
            st.session_state.active_dremio_sources = []
            st.session_state.source_relationships = []
            st.session_state.source_columns_by_path = {}
            st.rerun()


def render_auth_gate_bigdados() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        f"""
        <style>
          [data-testid="stSidebar"] {{ filter: blur(1.8px); opacity: 0.56; }}
          .bigdados-auth-shell {{ max-width: 620px; margin: 9vh auto 0 auto; display: flex; flex-direction: column; gap: 22px; }}
          .bigdados-auth-card {{ padding: 30px 34px; border-radius: 24px; border: 1px solid rgba(148, 163, 184, 0.28); background: rgba(255, 255, 255, 0.94); color: #0f172a; box-shadow: 0 26px 90px rgba(15, 23, 42, 0.16); }}
          .bigdados-auth-title {{ font-size: 30px; line-height: 1.16; font-weight: 850; letter-spacing: -0.03em; margin-bottom: 12px; }}
          .bigdados-auth-subtitle {{ color: #475569; font-size: 15px; line-height: 1.55; }}
          div[data-testid="stForm"] {{ max-width: 620px; margin: 22px auto 0 auto; padding: 18px 20px 14px 20px; border-radius: 16px; border: 1px solid rgba(148, 163, 184, 0.34); background: rgba(255, 255, 255, 0.88); box-shadow: 0 18px 50px rgba(15, 23, 42, 0.08); }}
          div[data-testid="stForm"] button[kind="primary"] {{ border-radius: 10px; margin-top: 8px; }}
          div[data-testid="stForm"] input {{ border-radius: 10px; }}
          .stAlert {{ max-width: 620px; margin-left: auto; margin-right: auto; }}
          @media (prefers-color-scheme: dark) {{
            .bigdados-auth-card {{ background: rgba(15, 23, 42, 0.88); color: #f8fafc; border-color: rgba(148, 163, 184, 0.24); box-shadow: 0 28px 90px rgba(0, 0, 0, 0.38); }}
            .bigdados-auth-subtitle {{ color: #cbd5e1; }}
            div[data-testid="stForm"] {{ background: rgba(15, 23, 42, 0.72); border-color: rgba(148, 163, 184, 0.24); box-shadow: 0 18px 60px rgba(0, 0, 0, 0.28); }}
          }}
        </style>
        <div class="bigdados-auth-shell">
          <div class="bigdados-auth-card">
            <div class="bigdados-auth-title">Desbloquear {APP_NAME}</div>
            <div class="bigdados-auth-subtitle">Use seu PAT do Dremio para validar permissões e identificar seu e-mail corporativo. O token fica somente em memória nesta sessão.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("dremio_pat_unlock_form"):
        pat = st.text_input("Personal Access Token do Dremio", value="", type="password", placeholder="Cole aqui o seu PAT do Dremio")
        submitted = st.form_submit_button("Desbloquear app", type="primary", use_container_width=True)

    if submitted:
        try:
            authenticator = DremioPATAuthenticator(base_app.DREMIO_CLOUD_HOST, base_app.DREMIO_CLOUD_PROJECT_ID, is_cloud=True)
            user = authenticator.authenticate(pat)
            st.session_state.authenticated = True
            st.session_state.user_email = user.email
            st.session_state.user_id = user.user_id
            st.session_state.dremio_pat = pat.strip()
            store = base_app.memory()
            if store:
                store.upsert_user(user.user_id, user.email)
                base_app.refresh_conversations()
            st.success(f"App desbloqueado para {user.email}.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não consegui validar o PAT no Dremio: {exc}")

    st.info("Depois de desbloquear, escolha a fonte Dremio ou Planilha na barra lateral para iniciar o agente.")
    return False


def render_chat_with_history_first():
    set_browser_title()
    st.title(f"📊 {home_title()}")
    st.caption(APP_CAPTION)

    if st.session_state.get("conversation_id"):
        st.caption(f"Conversa: `{st.session_state.conversation_id}`")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if not st.session_state.agent:
        st.info(NO_SOURCE_MESSAGE)
        return

    apply_agent_workspace_context()
    user_input = st.chat_input("Pergunte algo sobre os dados...")
    if not user_input:
        base_app.render_download_buttons()
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    base_app.append_persistent_message("user", user_input)

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
        base_app.render_download_buttons()

    result = getattr(st.session_state.agent, "last_query_result", None)
    st.session_state.messages.append({"role": "assistant", "content": response})
    base_app.append_persistent_message(
        "assistant",
        response,
        sql=getattr(result, "sql_executed", None),
        query_result_summary=base_app.result_summary(result),
    )

    if result:
        base_app.update_conversation_state(
            last_query_sql=result.sql_executed,
            last_result_summary=base_app.result_summary(result),
        )

    st.rerun()


if not hasattr(base_app, "_original_load_conversation"):
    base_app._original_load_conversation = base_app.load_conversation

base_app.render_sidebar = render_sidebar_bigdados
base_app.render_auth_gate = render_auth_gate_bigdados
base_app.render_chat = render_chat_with_history_first
base_app.load_conversation = load_conversation_bigdados

if __name__ == "__main__":
    base_app.main()
