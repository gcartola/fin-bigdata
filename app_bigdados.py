import base64
import re
from itertools import combinations
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Fonte única de configuração visual. O app.py legado também chama set_page_config;
# depois daqui, neutralizamos chamadas posteriores para evitar conflito de Streamlit.
st.set_page_config(page_title="BigDados", page_icon="🎲", layout="wide")
st.set_page_config = lambda *args, **kwargs: None

import app as base_app
from auth import DremioPATAuthenticator
from dremio_engine import DremioEngine

APP_NAME = "BigDados"
APP_CAPTION = "Bancada analítica para BigDados assistida por Agente Gemini"
NO_SOURCE_MESSAGE = "Escolha suas fontes de dados para iniciar ou continuar uma conversa"


def phase_state():
    if "active_dremio_sources" not in st.session_state:
        st.session_state.active_dremio_sources = []
    if "source_relationships" not in st.session_state:
        st.session_state.source_relationships = []
    if "source_columns_by_path" not in st.session_state:
        st.session_state.source_columns_by_path = {}
    if "show_source_manager" not in st.session_state:
        st.session_state.show_source_manager = False
    if "relationship_suggestions" not in st.session_state:
        st.session_state.relationship_suggestions = []
    if "source_data_profiles" not in st.session_state:
        st.session_state.source_data_profiles = {}
    if "editing_conversation_id" not in st.session_state:
        st.session_state.editing_conversation_id = None
    if "editing_conversation_title" not in st.session_state:
        st.session_state.editing_conversation_title = ""
    if "delete_conversation_id" not in st.session_state:
        st.session_state.delete_conversation_id = None


def load_asset_base64(candidates: list[str], fallback_base64: str | None = None) -> str:
    for candidate in candidates:
        path = Path(candidate)
        if path.exists() and path.is_file():
            return base64.b64encode(path.read_bytes()).decode("utf-8")
    return fallback_base64 or ""


BIGDADOS_FAVICON_BASE64 = load_asset_base64([
    "assets/icon-favicon-bd.png",
    "assets/favicon-bd.png",
    "assets/icon-bd.png",
])

BIGDADOS_LOGO_BASE64 = load_asset_base64([
    "assets/logo_bd.png",
    "assets/bigdados-logo.png",
    "assets/bigdados_logo.png",
    "assets/icon-bd.png",
], fallback_base64=BIGDADOS_FAVICON_BASE64)


def force_bigdados_branding():
    if not BIGDADOS_FAVICON_BASE64:
        return
    components.html(
        f"""
        <script>
        const title = "BigDados";
        const href = "data:image/png;base64,{BIGDADOS_FAVICON_BASE64}";
        function applyBranding() {{
          const doc = window.parent.document;
          if (doc.title !== title) doc.title = title;
          doc.querySelectorAll("link[rel~='icon'], link[rel='shortcut icon'], link[rel='apple-touch-icon']").forEach(el => el.remove());
          const icon = doc.createElement('link');
          icon.rel = 'icon';
          icon.type = 'image/png';
          icon.href = href;
          doc.head.appendChild(icon);
        }}
        applyBranding();
        setInterval(applyBranding, 1000);
        </script>
        """,
        height=0,
    )


def inject_sidebar_compact_css():
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 1.15rem; }
          [data-testid="stSidebar"] h1 { margin-top: 0 !important; padding-top: 0 !important; }
          [data-testid="stSidebar"] button p {
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
          }
          [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] { gap: 0.25rem; }
          [data-testid="stSidebar"] button[kind="tertiary"] {
            border: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
            padding-left: 0.1rem !important;
            padding-right: 0.1rem !important;
            min-height: 2rem !important;
          }
          [data-testid="stSidebar"] button[kind="tertiary"]:hover {
            background: rgba(148, 163, 184, 0.12) !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


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
    current.append({"type": "dremio_view", "path": path, "name": name, "alias": source_alias_from_name(name)})
    st.session_state.active_dremio_sources = current
    st.success(f"Adicionei {name} às fontes da análise.")


def persist_relationships():
    relationships = st.session_state.get("source_relationships", [])
    base_app.update_conversation_state(relationships=relationships)
    apply_agent_workspace_context()


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
    return f"{rel.get('left_name')}.{rel.get('left_column')} = {rel.get('right_name')}.{rel.get('right_column')}"


def get_dremio_engine_for_metadata() -> DremioEngine | None:
    pat = st.session_state.get("dremio_pat")
    if not pat:
        return None
    engine = st.session_state.get("dremio_engine")
    if engine:
        return engine
    paths = [src["path"] for src in st.session_state.get("active_dremio_sources", [])]
    return DremioEngine(base_app.DREMIO_CLOUD_HOST, pat, base_app.DREMIO_CLOUD_PROJECT_ID, is_cloud=True, allowed_paths=paths)


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


def normalize_column_name(name: str) -> str:
    value = (name or "").lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    aliases = {
        "num": "numero",
        "nr": "numero",
        "cod": "codigo",
        "id": "codigo",
        "cpfcnpj": "cpf_cnpj",
        "cpf_cnpj_cliente": "cpf_cnpj",
        "cnpj_cpf": "cpf_cnpj",
        "contrato_cliente": "contrato",
        "numero_do_contrato": "numero_contrato",
        "num_contrato": "numero_contrato",
        "nr_contrato": "numero_contrato",
        "codigo_contrato": "numero_contrato",
        "contrato": "numero_contrato",
        "cod_venda_mega": "codigo_venda_mega",
        "codigo_venda": "codigo_venda_mega",
    }
    return aliases.get(value, value)


def token_set(name: str) -> set[str]:
    normalized = normalize_column_name(name)
    return {token for token in normalized.split("_") if token}


def score_column_pair(left_col: str, right_col: str) -> tuple[float, list[str]]:
    left_norm = normalize_column_name(left_col)
    right_norm = normalize_column_name(right_col)
    left_tokens = token_set(left_col)
    right_tokens = token_set(right_col)
    reasons = []
    score = 0.0

    if left_norm == right_norm:
        score += 0.72
        reasons.append("nome normalizado igual")
    elif left_norm in right_norm or right_norm in left_norm:
        score += 0.48
        reasons.append("nome parecido/contido")
    else:
        intersection = left_tokens & right_tokens
        union = left_tokens | right_tokens
        if union:
            overlap = len(intersection) / len(union)
            score += overlap * 0.44
            if intersection:
                reasons.append(f"tokens em comum: {', '.join(sorted(intersection))}")

    key_groups = [
        {"contrato", "numero_contrato"}, {"cpf", "cnpj", "cpf_cnpj"},
        {"cliente", "codigo_cliente", "cod_cliente"}, {"venda", "codigo_venda", "codigo_venda_mega"},
        {"empreendimento", "obra", "projeto"}, {"unidade", "apto", "bloco"},
    ]
    left_joined = "_".join(sorted(left_tokens | {left_norm}))
    right_joined = "_".join(sorted(right_tokens | {right_norm}))
    for group in key_groups:
        if any(term in left_joined for term in group) and any(term in right_joined for term in group):
            score += 0.2
            reasons.append(f"termo de chave provável: {sorted(group)[0]}")
            break

    if left_col == right_col:
        score += 0.08
        reasons.append("nome original igual")
    if any(term in left_norm for term in ["data", "valor", "desc", "nome", "status"]):
        score -= 0.16
        reasons.append("campo pode ser descritivo/medida, validar antes de cruzar")

    score = max(0.0, min(round(score, 2), 0.99))
    return score, reasons or ["similaridade baixa"]


def confidence_label(score: float) -> str:
    if score >= 0.85:
        return "alta"
    if score >= 0.65:
        return "média"
    return "baixa"


def generate_relationship_suggestions(limit: int = 20) -> list[dict]:
    phase_state()
    sources = st.session_state.get("active_dremio_sources", [])
    if len(sources) < 2:
        return []
    suggestions = []
    for left, right in combinations(sources, 2):
        left_columns = load_columns_for_source(left["path"])
        right_columns = load_columns_for_source(right["path"])
        for left_col in left_columns:
            for right_col in right_columns:
                score, reasons = score_column_pair(left_col, right_col)
                if score < 0.45:
                    continue
                suggestions.append({
                    "left_path": left["path"], "left_name": left["name"], "left_alias": left["alias"], "left_column": left_col,
                    "right_path": right["path"], "right_name": right["name"], "right_alias": right["alias"], "right_column": right_col,
                    "score": score, "confidence": f"auto_{confidence_label(score)}", "reasons": reasons,
                })
    suggestions.sort(key=lambda item: item["score"], reverse=True)
    st.session_state.relationship_suggestions = suggestions[:limit]
    return st.session_state.relationship_suggestions


def quote_identifier(column: str) -> str:
    return '"' + column.replace('"', '""') + '"'


def profile_column(path: str, column: str) -> dict:
    engine = get_dremio_engine_for_metadata()
    if not engine:
        raise RuntimeError("Dremio não conectado.")
    col = quote_identifier(column)
    query = f'''
SELECT
  COUNT(*) AS total_linhas,
  COUNT({col}) AS valores_preenchidos,
  COUNT(DISTINCT {col}) AS valores_distintos,
  MIN(CAST({col} AS VARCHAR)) AS menor_valor_amostra,
  MAX(CAST({col} AS VARCHAR)) AS maior_valor_amostra
FROM {path}
'''.strip()
    result = engine.run_sql(query)
    values = result.rows[0] if result.rows else []
    return {
        "path": path,
        "column": column,
        "total_linhas": values[0] if len(values) > 0 else None,
        "valores_preenchidos": values[1] if len(values) > 1 else None,
        "valores_distintos": values[2] if len(values) > 2 else None,
        "menor_valor_amostra": values[3] if len(values) > 3 else None,
        "maior_valor_amostra": values[4] if len(values) > 4 else None,
    }


def profile_key(path: str, column: str) -> str:
    return f"{path}::{column}"


def save_profile(profile: dict):
    profiles = st.session_state.get("source_data_profiles", {})
    profiles[profile_key(profile["path"], profile["column"])] = profile
    st.session_state.source_data_profiles = profiles
    base_app.update_conversation_state(data_profiles=profiles)
    apply_agent_workspace_context()


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
        "left_path": left_path, "left_name": left["name"], "left_alias": left["alias"], "left_column": left_column,
        "right_path": right_path, "right_name": right["name"], "right_alias": right["alias"], "right_column": right_column,
        "confidence": "manual",
    }
    existing = st.session_state.get("source_relationships", [])
    signature = (left_path, left_column, right_path, right_column)
    reverse = (right_path, right_column, left_path, left_column)
    for rel in existing:
        rel_signature = (rel.get("left_path"), rel.get("left_column"), rel.get("right_path"), rel.get("right_column"))
        if rel_signature in (signature, reverse):
            st.info("Esse relacionamento já existe.")
            return
    existing.append(relationship)
    st.session_state.source_relationships = existing
    persist_relationships()
    st.success(f"Relacionamento criado: {relationship_label(relationship)}")


def add_suggested_relationship(suggestion: dict):
    existing = st.session_state.get("source_relationships", [])
    signature = (suggestion.get("left_path"), suggestion.get("left_column"), suggestion.get("right_path"), suggestion.get("right_column"))
    reverse = (suggestion.get("right_path"), suggestion.get("right_column"), suggestion.get("left_path"), suggestion.get("left_column"))
    for rel in existing:
        rel_signature = (rel.get("left_path"), rel.get("left_column"), rel.get("right_path"), rel.get("right_column"))
        if rel_signature in (signature, reverse):
            st.info("Esse relacionamento já existe.")
            return
    existing.append({**suggestion, "reasons": suggestion.get("reasons", [])})
    st.session_state.source_relationships = existing
    persist_relationships()
    st.success(f"Relacionamento adicionado: {relationship_label(suggestion)}")


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
    engine = DremioEngine(base_app.DREMIO_CLOUD_HOST, pat, base_app.DREMIO_CLOUD_PROJECT_ID, is_cloud=True, allowed_paths=paths)
    tables = engine.list_tables()
    loaded = [f"Dremio · {len(paths)} view(s) selecionada(s)"] + [f"{src['name']} — {src['path']}" for src in sources]
    st.session_state.dremio_engine = engine
    st.session_state.dremio_loaded_files = loaded
    base_app.activate_engine(engine, loaded, f"Dremio conectado com {len(paths)} view(s).", {
        "selected_dremio_view": paths[0] if len(paths) == 1 else None,
        "dremio_sources": sources,
        "relationships": st.session_state.get("source_relationships", []),
        "active_sources": loaded,
    })
    apply_agent_workspace_context()
    if len(tables) != len(paths):
        st.caption(f"Aviso técnico: o engine expôs {len(tables)} tabela(s)/view(s) para {len(paths)} path(s) selecionado(s).")
    return True


def clear_active_sources():
    st.session_state.active_dremio_sources = []
    st.session_state.source_relationships = []
    st.session_state.source_columns_by_path = {}
    st.session_state.relationship_suggestions = []
    st.session_state.source_data_profiles = {}
    st.session_state.dremio_engine = None
    st.session_state.spreadsheet_engine = None
    st.session_state.engine = None
    st.session_state.agent = None
    st.session_state.loaded_files = []
    st.session_state.dremio_loaded_files = []
    st.session_state.spreadsheet_loaded_files = []
    st.session_state.pending_source_metadata = {}
    base_app.update_conversation_state(active_sources=[], dremio_sources=[], relationships=[], data_profiles={}, selected_dremio_view="")


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
    if sources:
        if st.button("🗑️ Limpar fontes selecionadas", use_container_width=True, key="clear_selected_sources"):
            clear_active_sources()
            st.rerun()
    else:
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
            st.caption(f"Confiança: {rel.get('confidence', 'manual')}")
        with col_b:
            if st.button("Remover", key=f"remove_relationship_{idx}"):
                remove_relationship(idx)
                st.rerun()


def render_relationship_suggestions():
    phase_state()
    st.markdown("#### Sugestões automáticas")
    sources = st.session_state.get("active_dremio_sources", [])
    if len(sources) < 2:
        st.info("Adicione pelo menos duas views para gerar sugestões.")
        return
    st.caption("As sugestões usam similaridade de nomes de colunas e termos de chave prováveis. Use o score como triagem, não como verdade absoluta.")
    if st.button("Gerar sugestões de relacionamento", type="primary", use_container_width=True, key="generate_relationship_suggestions"):
        try:
            suggestions = generate_relationship_suggestions()
            st.success(f"Gerei {len(suggestions)} sugestão(ões).") if suggestions else st.warning("Não encontrei sugestões com score mínimo.")
        except Exception as exc:
            st.error(f"Falha ao gerar sugestões: {exc}")

    for idx, suggestion in enumerate(st.session_state.get("relationship_suggestions", []), start=1):
        score = suggestion["score"]
        st.markdown(f"**{idx}. {suggestion['left_name']}.{suggestion['left_column']} = {suggestion['right_name']}.{suggestion['right_column']}**")
        st.caption(f"Score: {score:.2f} · Confiança: {confidence_label(score)} · Motivos: {'; '.join(suggestion.get('reasons', []))}")
        col1, col2, _ = st.columns([1, 1, 3])
        with col1:
            if st.button("Usar", key=f"use_suggestion_{idx}"):
                add_suggested_relationship(suggestion)
                st.rerun()
        with col2:
            if st.button("Perfilar", key=f"profile_suggestion_{idx}"):
                try:
                    save_profile(profile_column(suggestion["left_path"], suggestion["left_column"]))
                    save_profile(profile_column(suggestion["right_path"], suggestion["right_column"]))
                    st.success("Perfil das duas colunas calculado.")
                except Exception as exc:
                    st.error(f"Falha ao calcular perfil: {exc}")
        st.divider()


def render_data_profile():
    phase_state()
    st.markdown("#### Perfil de dados")
    sources = st.session_state.get("active_dremio_sources", [])
    if not sources:
        st.info("Adicione uma fonte para calcular perfil de dados.")
        return
    source_options = {f"{src['name']} · {idx}": src for idx, src in enumerate(sources, start=1)}
    selected_label = st.selectbox("Fonte", list(source_options.keys()), key="profile_source")
    source = source_options[selected_label]
    columns = load_columns_for_source(source["path"])
    column = st.selectbox("Coluna", columns or [""], key="profile_column")
    if st.button("Calcular perfil da coluna", type="primary", use_container_width=True, key="calculate_column_profile"):
        try:
            save_profile(profile_column(source["path"], column))
            st.success("Perfil calculado e salvo na conversa.")
        except Exception as exc:
            st.error(f"Falha ao calcular perfil: {exc}")
    profiles = st.session_state.get("source_data_profiles", {})
    if not profiles:
        st.caption("Nenhum perfil salvo ainda.")
        return
    st.markdown("##### Perfis salvos")
    for profile in profiles.values():
        st.markdown(f"**{source_name_from_path(profile.get('path', ''))}.{profile.get('column')}**")
        st.caption(
            f"Linhas: {profile.get('total_linhas')} · Preenchidas: {profile.get('valores_preenchidos')} · "
            f"Distintas: {profile.get('valores_distintos')} · Min/Max amostra: {profile.get('menor_valor_amostra')} / {profile.get('maior_valor_amostra')}"
        )


def render_source_manager_content():
    phase_state()
    tab_dremio, tab_planilha, tab_conectadas, tab_relacionamentos, tab_sugestoes, tab_perfil = st.tabs([
        "Dremio", "Planilha", "Fontes conectadas", "Relacionamentos", "Sugestões", "Perfil de dados"
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
    with tab_sugestoes:
        render_relationship_suggestions()
    with tab_perfil:
        render_data_profile()


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


def build_agent_context() -> str:
    sources = st.session_state.get("active_dremio_sources", [])
    relationships = st.session_state.get("source_relationships", [])
    suggestions = st.session_state.get("relationship_suggestions", [])[:5]
    profiles = st.session_state.get("source_data_profiles", {})
    if not sources and not relationships and not suggestions and not profiles:
        return ""

    lines = ["\n\nCONTEXTO DO WORKSPACE BIGDADOS:", "As fontes abaixo foram selecionadas pelo usuário para esta conversa."]
    if sources:
        lines.append("\nFontes ativas:")
        for src in sources:
            lines.append(f"- alias `{src.get('alias')}` | nome `{src.get('name')}` | path {src.get('path')}")
            cols = st.session_state.get("source_columns_by_path", {}).get(src.get("path"), [])
            if cols:
                lines.append(f"  colunas disponíveis: {', '.join(cols[:80])}")
    if relationships:
        lines.append("\nRelacionamentos conhecidos definidos pelo usuário:")
        for rel in relationships:
            lines.append(
                f"- `{rel.get('left_name')}`.`{rel.get('left_column')}` = `{rel.get('right_name')}`.`{rel.get('right_column')}` "
                f"(confiança: {rel.get('confidence', 'manual')}, score: {rel.get('score', 'manual')})"
            )
        lines.append("\nQuando o usuário pedir análise cruzada entre fontes, use esses relacionamentos como chaves preferenciais. Se a junção puder duplicar linhas, avise e valide contagens/amostras antes de concluir.")
    if suggestions:
        lines.append("\nSugestões automáticas recentes de relacionamento:")
        for item in suggestions:
            lines.append(f"- {item.get('left_name')}.{item.get('left_column')} = {item.get('right_name')}.{item.get('right_column')} score={item.get('score')} confiança={item.get('confidence')}")
    if profiles:
        lines.append("\nPerfis de dados calculados:")
        for profile in profiles.values():
            lines.append(f"- {source_name_from_path(profile.get('path', ''))}.{profile.get('column')}: linhas={profile.get('total_linhas')}, preenchidas={profile.get('valores_preenchidos')}, distintas={profile.get('valores_distintos')}")
    if suggestions or profiles:
        lines.append("\nUse score/perfil como apoio. Não trate sugestão automática como relacionamento confirmado se ela não estiver em Relacionamentos conhecidos.")
    return "\n".join(lines)


def apply_agent_workspace_context():
    agent = st.session_state.get("agent")
    if not agent:
        return
    if not hasattr(agent, "base_system"):
        agent.base_system = agent.system
    agent.system = agent.base_system + build_agent_context()


def hydrate_workspace_from_conversation(conversation_id: str):
    store = base_app.memory()
    if not store or str(conversation_id).startswith("local-"):
        return
    conversation = store.get_conversation(conversation_id)
    if not conversation:
        return
    st.session_state.active_dremio_sources = conversation.get("dremio_sources") or []
    st.session_state.source_relationships = conversation.get("relationships") or []
    st.session_state.source_data_profiles = conversation.get("data_profiles") or {}
    st.session_state.pending_source_metadata = {
        **dict(st.session_state.get("pending_source_metadata") or {}),
        "dremio_sources": st.session_state.active_dremio_sources,
        "relationships": st.session_state.source_relationships,
        "data_profiles": st.session_state.source_data_profiles,
    }
    apply_agent_workspace_context()


def scalar_for_firestore(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def query_result_payload(result, max_rows: int = 80) -> dict | None:
    if not result or not getattr(result, "rows", None):
        return None
    columns = list(result.columns)
    rows = []
    for row in result.rows[:max_rows]:
        rows.append({col: scalar_for_firestore(value) for col, value in zip(columns, row)})
    return {
        "columns": columns,
        "rows": rows,
        "sample_row_count": len(rows),
        "row_count": int(result.row_count or len(rows)),
        "sql_executed": getattr(result, "sql_executed", None),
        "execution_time_ms": getattr(result, "execution_time_ms", None),
    }


def dataframe_from_payload(payload: dict) -> pd.DataFrame:
    return pd.DataFrame(payload.get("rows") or [], columns=payload.get("columns") or [])


def render_copy_sql_button(sql: str, key: str):
    if not sql:
        return
    components.html(
        f"""
        <button id="copy-sql-{key}" style="width:100%;border:1px solid rgba(148,163,184,.35);border-radius:10px;padding:9px 12px;background:transparent;color:inherit;font-weight:650;cursor:pointer;">Copiar SQL</button>
        <script>
          const btn = document.getElementById('copy-sql-{key}');
          btn.onclick = async () => {{
            try {{ await navigator.clipboard.writeText({sql!r}); btn.innerText = 'SQL copiado'; setTimeout(() => btn.innerText = 'Copiar SQL', 1600); }}
            catch (err) {{ btn.innerText = 'Não consegui copiar'; setTimeout(() => btn.innerText = 'Copiar SQL', 1600); }}
          }};
        </script>
        """,
        height=46,
    )


def render_payload_result_block(payload: dict, key: str = "persisted"):
    if not payload or not payload.get("rows"):
        return
    df = dataframe_from_payload(payload)
    total_rows = payload.get("row_count") or len(df)
    sample_rows = payload.get("sample_row_count") or len(df)
    sql = payload.get("sql_executed") or ""
    st.markdown("### Resultado da consulta")
    with st.container(border=True):
        caption = f"{total_rows:,} linha(s) retornada(s) · {len(df.columns)} coluna(s)"
        if sample_rows < total_rows:
            caption += f" · exibindo amostra persistida de {sample_rows:,} linha(s)"
        if payload.get("execution_time_ms"):
            caption += f" · {payload.get('execution_time_ms')}ms"
        st.caption(caption)
        st.dataframe(df, use_container_width=True, hide_index=True)
        with st.expander("SQL gerado", expanded=False):
            if sql:
                render_copy_sql_button(sql, key)
                st.code(sql, language="sql")
            else:
                st.caption("Nenhum SQL registrado para este resultado.")


def strip_markdown_tables(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        is_table_line = stripped.startswith("|") and stripped.endswith("|")
        is_separator = bool(re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", stripped))
        if is_table_line or is_separator:
            in_table = True
            continue
        if in_table and not stripped:
            in_table = False
            continue
        in_table = False
        cleaned.append(line)
    return "\n".join(cleaned)


def clean_agent_response_for_structured_result(text: str) -> str:
    if not text:
        return text
    cleaned = text.strip()
    cleaned = re.sub(r"(?is)\n*\*{0,2}\s*SQL\s+(utilizado|gerado|usado|que usei)\s*:?\s*\*{0,2}\s*```sql.*?```", "\n", cleaned)
    cleaned = re.sub(r"(?is)\n*\*{0,2}\s*SQL\s+(utilizado|gerado|usado|que usei)\s*:?\s*\*{0,2}\s*```.*?```", "\n", cleaned)
    cleaned = re.sub(r"(?is)```sql.*?```", "\n", cleaned)
    cleaned = strip_markdown_tables(cleaned)
    cleaned_lines = []
    for line in cleaned.splitlines():
        normalized = line.strip().lower()
        if not normalized:
            cleaned_lines.append(line)
            continue
        if normalized.startswith("certo") and ("aqui estão" in normalized or "segue" in normalized):
            continue
        if normalized.startswith("aqui estão") or normalized.startswith("segue o resultado"):
            continue
        if re.match(r"^\*{0,2}\s*sql\s+(utilizado|gerado|usado|que usei)\s*:?\s*\*{0,2}$", normalized):
            continue
        cleaned_lines.append(line)
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned_lines)).strip()
    return cleaned or "Analisei o resultado acima."


def append_persistent_message(role: str, content: str, **metadata):
    conversation_id = base_app.ensure_conversation(title=base_app.build_conversation_title(content) if role == "user" else None)
    store = base_app.memory()
    if store and conversation_id and not str(conversation_id).startswith("local-"):
        store.append_message(conversation_id, role, content, **metadata)
        query_result = metadata.get("query_result")
        if query_result:
            store.update_conversation(
                conversation_id,
                latest_query_result=query_result,
                last_query_sql=query_result.get("sql_executed"),
                last_result_summary=metadata.get("query_result_summary"),
            )
    else:
        base_app.upsert_local_conversation(conversation_id, base_app.build_conversation_title(content) if role == "user" else None)
    base_app.refresh_conversations()


def load_conversation(conversation_id: str):
    store = base_app.memory()
    messages = []
    conversation = None
    if store and not str(conversation_id).startswith("local-"):
        messages = store.get_messages(conversation_id, limit=50)
        conversation = store.get_conversation(conversation_id)
    hydrated = []
    for m in messages:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        item = {"role": role, "content": m.get("content", "")}
        if m.get("query_result"):
            item["query_result"] = m.get("query_result")
        hydrated.append(item)
    latest_result = (conversation or {}).get("latest_query_result")
    if latest_result and hydrated:
        for item in reversed(hydrated):
            if item.get("role") == "assistant":
                item.setdefault("query_result", latest_result)
                break
    st.session_state.conversation_id = conversation_id
    st.session_state.messages = hydrated
    if st.session_state.get("agent"):
        st.session_state.agent.load_history(st.session_state.messages)
    hydrate_workspace_from_conversation(conversation_id)


def short_title(title: str, max_chars: int = 28) -> str:
    title = " ".join((title or "Conversa sem título").split())
    return title if len(title) <= max_chars else title[: max_chars - 3].rstrip() + "..."


def rename_conversation(conversation_id: str, title: str):
    title = (title or "").strip()
    if not title:
        st.warning("Informe um nome para a conversa.")
        return
    store = base_app.memory()
    if not store:
        st.error("Memória persistente indisponível.")
        return
    store.update_conversation(conversation_id, title=title)
    base_app.refresh_conversations()
    st.session_state.editing_conversation_id = None
    st.session_state.editing_conversation_title = ""


def delete_conversation(conversation_id: str):
    store = base_app.memory()
    if not store:
        st.error("Memória persistente indisponível.")
        return
    store.update_conversation(conversation_id, status="deleted")
    if st.session_state.get("conversation_id") == conversation_id:
        st.session_state.conversation_id = None
        st.session_state.messages = []
        if st.session_state.get("agent"):
            st.session_state.agent.load_history([])
    base_app.refresh_conversations()


def render_conversation_sidebar():
    phase_state()
    st.markdown("### Conversas")
    if st.button("Nova conversa", use_container_width=True):
        base_app.new_conversation()
    base_app.refresh_conversations()
    conversations = st.session_state.get("saved_conversations", [])
    if not conversations:
        st.caption("Memória persistente indisponível; a conversa atual fica só nesta sessão." if st.session_state.get("memory_error") else "Nenhuma conversa iniciada ainda.")
        return
    current = st.session_state.get("conversation_id")
    for conv in conversations:
        conv_id = conv.get("id")
        title = conv.get("title") or "Conversa sem título"
        is_current = conv_id == current
        if st.session_state.editing_conversation_id == conv_id:
            new_title = st.text_input("Nome da conversa", value=st.session_state.editing_conversation_title or title, key=f"edit_title_{conv_id}", label_visibility="collapsed")
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("Salvar", key=f"save_title_{conv_id}", use_container_width=True):
                    rename_conversation(conv_id, new_title)
                    st.rerun()
            with col_cancel:
                if st.button("Cancelar", key=f"cancel_title_{conv_id}", use_container_width=True):
                    st.session_state.editing_conversation_id = None
                    st.session_state.editing_conversation_title = ""
                    st.rerun()
            continue
        if st.session_state.delete_conversation_id == conv_id:
            st.warning(f"Apagar: {short_title(title, 34)}?")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("Apagar", key=f"confirm_delete_{conv_id}", use_container_width=True):
                    delete_conversation(conv_id)
                    st.session_state.delete_conversation_id = None
                    st.rerun()
            with col_no:
                if st.button("Cancelar", key=f"cancel_delete_{conv_id}", use_container_width=True):
                    st.session_state.delete_conversation_id = None
                    st.rerun()
            continue
        col_open, col_edit, col_delete = st.columns([8, 1, 1], gap="small")
        with col_open:
            label = f"{'✅ ' if is_current else ''}{short_title(title)}"
            if st.button(label, key=f"open_conversation_{conv_id}", use_container_width=True, disabled=is_current, help=title):
                load_conversation(conv_id)
                st.rerun()
        with col_edit:
            if st.button("✏️", key=f"edit_conversation_{conv_id}", help="Renomear conversa", type="tertiary"):
                st.session_state.editing_conversation_id = conv_id
                st.session_state.editing_conversation_title = title
                st.rerun()
        with col_delete:
            if st.button("🗑️", key=f"delete_conversation_{conv_id}", help="Apagar conversa", type="tertiary"):
                st.session_state.delete_conversation_id = conv_id
                st.rerun()
    if st.session_state.get("memory_error"):
        st.caption("Firestore indisponível. Persistência real será retomada quando a API estiver ativa.")


def render_sidebar():
    force_bigdados_branding()
    inject_sidebar_compact_css()
    phase_state()
    _, _, model = base_app.get_vertex_config()
    with st.sidebar:
        st.title(APP_NAME)
        st.caption("Análises de BigDados")
        st.caption(f"Modelo: `{model}`")
        if st.session_state.get("authenticated"):
            st.caption(f"Usuário: `{st.session_state.get('user_email')}`")
            if st.button("Trocar PAT / sair", use_container_width=True):
                base_app.reset_workspace(keep_auth=False)
                clear_active_sources()
                st.rerun()
        else:
            st.warning("App bloqueado. Informe seu PAT para liberar o agente.")
        st.divider()
        render_source_summary_sidebar()
        if st.session_state.get("authenticated"):
            st.divider()
            render_conversation_sidebar()


def render_auth_gate() -> bool:
    force_bigdados_branding()
    if st.session_state.get("authenticated"):
        return True
    st.markdown(
        f"""
        <style>
          [data-testid="stSidebar"] {{ filter: blur(1.8px); opacity: 0.56; }}
          .bigdados-auth-shell {{ max-width: 560px; margin: 2.2vh auto 0 auto; display:flex; flex-direction:column; gap:10px; align-items:stretch; }}
          .bigdados-login-logo {{ display:block; width:min(220px, 38vw); max-height:128px; object-fit:contain; margin:0 auto; }}
          .bigdados-auth-card {{ padding:20px 26px; border-radius:22px; border:1px solid color-mix(in srgb, var(--text-color) 18%, transparent); background:color-mix(in srgb, var(--secondary-background-color) 92%, transparent); color:var(--text-color); box-shadow:0 18px 60px rgba(0,0,0,.18); }}
          .bigdados-auth-title {{ font-size:26px; line-height:1.12; font-weight:850; letter-spacing:-.03em; margin-bottom:8px; color:var(--text-color); }}
          .bigdados-auth-subtitle {{ color:color-mix(in srgb, var(--text-color) 72%, transparent); font-size:14px; line-height:1.42; }}
          .bigdados-auth-input-wrap {{ max-width:560px; margin:10px auto 0 auto; padding:14px 16px 12px 16px; border-radius:16px; border:1px solid color-mix(in srgb, var(--text-color) 18%, transparent); background:color-mix(in srgb, var(--secondary-background-color) 88%, transparent); color:var(--text-color); box-shadow:0 14px 42px rgba(0,0,0,.14); }}
          .stAlert {{ max-width:560px; margin-left:auto; margin-right:auto; }}
        </style>
        <div class="bigdados-auth-shell">
          <img class="bigdados-login-logo" src="data:image/png;base64,{BIGDADOS_LOGO_BASE64}" />
          <div class="bigdados-auth-card">
            <div class="bigdados-auth-title">Desbloquear {APP_NAME}</div>
            <div class="bigdados-auth-subtitle">Use seu PAT do Dremio para validar permissões e identificar seu e-mail corporativo. O token fica somente em memória nesta sessão.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container():
        st.markdown('<div class="bigdados-auth-input-wrap">', unsafe_allow_html=True)
        pat = st.text_input("Personal Access Token do Dremio", value="", type="password", placeholder="Cole aqui o seu PAT do Dremio", key="safe_dremio_pat_unlock")
        submitted = st.button("Desbloquear app", type="primary", use_container_width=True, key="safe_unlock_button")
        st.markdown('</div>', unsafe_allow_html=True)
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


def render_messages_with_persisted_results():
    for index, msg in enumerate(st.session_state.get("messages", [])):
        with st.chat_message(msg["role"]):
            if msg.get("role") == "assistant" and msg.get("query_result"):
                render_payload_result_block(msg["query_result"], key=f"msg_{index}")
            st.markdown(msg.get("content", ""))


def render_chat():
    force_bigdados_branding()
    st.title(f"📊 {home_title()}")
    st.caption(APP_CAPTION)
    if st.session_state.get("conversation_id"):
        st.caption(f"Conversa: `{st.session_state.conversation_id}`")
    render_messages_with_persisted_results()
    if not st.session_state.agent:
        st.info(NO_SOURCE_MESSAGE)
        return
    apply_agent_workspace_context()
    user_input = st.chat_input("Pergunte algo sobre os dados...")
    if not user_input:
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
            raw_response = st.session_state.agent.chat(user_input, progress_callback=update_status)
        except Exception as exc:
            raw_response = f"Erro ao processar pergunta: {exc}"
            update_status("❌ Erro ao processar pergunta")
        status_box.empty()
        result = getattr(st.session_state.agent, "last_query_result", None)
        response = clean_agent_response_for_structured_result(raw_response) if result else raw_response
        payload = query_result_payload(result, max_rows=500)
        if payload:
            render_payload_result_block(payload, key="new_result")
        st.markdown(response)

    result = getattr(st.session_state.agent, "last_query_result", None)
    payload = query_result_payload(result, max_rows=500)
    response = clean_agent_response_for_structured_result(raw_response) if result else raw_response
    assistant_message = {"role": "assistant", "content": response}
    if payload:
        assistant_message["query_result"] = payload
    st.session_state.messages.append(assistant_message)
    append_persistent_message(
        "assistant",
        response,
        sql=getattr(result, "sql_executed", None),
        query_result_summary=base_app.result_summary(result),
        query_result=payload,
    )
    if result:
        base_app.update_conversation_state(last_query_sql=result.sql_executed, last_result_summary=base_app.result_summary(result))
    st.rerun()


def render_live_result_block(result=None):
    agent = st.session_state.get("agent")
    result = result or (getattr(agent, "last_query_result", None) if agent else None)
    payload = query_result_payload(result, max_rows=500)
    if not payload:
        return
    key = f"live_{len(st.session_state.get('messages', []))}_{abs(hash(payload.get('sql_executed') or ''))}"
    render_payload_result_block(payload, key=key)


def main():
    base_app.init_state()
    phase_state()
    base_app.render_sidebar()
    if not base_app.render_auth_gate():
        return
    base_app.render_chat()


base_app.render_sidebar = render_sidebar
base_app.render_auth_gate = render_auth_gate
base_app.render_chat = render_chat
base_app.render_download_buttons = render_live_result_block
base_app.append_persistent_message = append_persistent_message
base_app.load_conversation = load_conversation

if __name__ == "__main__":
    main()
