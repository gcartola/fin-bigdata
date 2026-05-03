import streamlit as st

import app_bigdados as app

_ORIGINAL_AUTH_GATE = app.render_auth_gate

AUTH_BOX_WIDTH = "min(448px, 92vw)"


def inject_auth_visual_refinement():
    st.markdown(
        f"""
        <style>
          main .block-container {{
            padding-top: 0.75rem !important;
            padding-bottom: 1rem !important;
          }}

          .bigdados-auth-shell {{
            width: {AUTH_BOX_WIDTH} !important;
            max-width: 448px !important;
            margin: 0.8rem auto 0 auto !important;
            gap: 0 !important;
            align-items: stretch !important;
          }}

          .bigdados-login-logo {{ display: none !important; }}

          .bigdados-auth-card {{
            width: 100% !important;
            box-sizing: border-box !important;
            padding: 18px 22px !important;
            border-radius: 20px !important;
            background: color-mix(in srgb, var(--secondary-background-color) 70%, transparent) !important;
            border-color: color-mix(in srgb, var(--text-color) 10%, transparent) !important;
          }}

          .bigdados-auth-title {{ font-size: 22px !important; margin-bottom: 8px !important; }}
          .bigdados-auth-subtitle {{
            font-size: 12.5px !important;
            line-height: 1.38 !important;
            font-weight: 560 !important;
            color: color-mix(in srgb, var(--text-color) 82%, transparent) !important;
          }}

          .bigdados-auth-input-wrap {{
            width: {AUTH_BOX_WIDTH} !important;
            max-width: 448px !important;
            margin: 12px auto 0 auto !important;
            padding: 0 !important;
            border: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
          }}

          .bigdados-auth-input-wrap div[data-testid="stTextInput"],
          .bigdados-auth-input-wrap div[data-testid="stButton"] {{
            width: 100% !important;
            max-width: 448px !important;
            margin-left: 0 !important;
            margin-right: 0 !important;
          }}

          .bigdados-auth-input-wrap div[data-testid="stButton"] {{ margin-top: 8px !important; }}

          main .stAlert {{
            width: {AUTH_BOX_WIDTH} !important;
            max-width: 448px !important;
            margin: 12px auto 0 auto !important;
          }}
          main .stAlert > div {{ width: 100% !important; box-sizing: border-box !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_mobile_visual_refinement():
    """Ajustes finos para uso real no celular, sem esconder sidebar nem conteúdo central."""
    st.markdown(
        """
        <style>
          main .block-container { padding-top: 0 !important; margin-top: 0 !important; }
          main h1 { margin-top: 0 !important; padding-top: 0 !important; }
          main h1:first-of-type {
            margin-block-start: 0 !important;
            margin-bottom: 0.55rem !important;
            line-height: 1.08 !important;
          }
          main [data-testid="stVerticalBlock"] > [style*="flex-direction: column"] { gap: 0.6rem !important; }

          [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            align-items: center !important;
            gap: 0.28rem !important;
          }
          [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div {
            min-width: 0 !important;
            width: auto !important;
            flex: 0 0 auto !important;
          }
          [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:first-child {
            flex: 1 1 auto !important;
            min-width: 0 !important;
          }
          [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:not(:first-child) {
            flex: 0 0 2.35rem !important;
            max-width: 2.35rem !important;
          }
          [data-testid="stSidebar"] button { min-width: 0 !important; }
          [data-testid="stSidebar"] button p {
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
          }
          [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] button {
            min-height: 2.3rem !important;
            height: 2.3rem !important;
            padding: 0.18rem 0.35rem !important;
          }
          [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:not(:first-child) button {
            width: 2.25rem !important;
            padding-left: 0 !important;
            padding-right: 0 !important;
          }

          div[data-testid="stDialog"], div[role="dialog"] {
            position: fixed !important;
            inset: 0 !important;
            overflow: hidden !important;
          }
          div[data-testid="stDialog"] > div, div[role="dialog"] > div {
            max-height: calc(100dvh - 2.2rem) !important;
            overflow-y: auto !important;
            overscroll-behavior: contain !important;
          }
          div[data-testid="stDialog"] section, div[role="dialog"] section {
            max-height: calc(100dvh - 2.2rem) !important;
            overflow-y: auto !important;
          }
          div[data-testid="stDialog"] [data-testid="stTabs"] button,
          div[role="dialog"] [data-testid="stTabs"] button {
            padding-left: 0.55rem !important;
            padding-right: 0.55rem !important;
            font-size: 0.92rem !important;
          }

          @media (max-width: 700px) {
            main .block-container {
              padding-top: 0 !important;
              padding-left: 1rem !important;
              padding-right: 1rem !important;
            }
            main h1:first-of-type {
              font-size: clamp(2.45rem, 12vw, 4.7rem) !important;
              line-height: 1.08 !important;
              letter-spacing: -0.045em !important;
            }
            div[data-testid="stDialog"] > div, div[role="dialog"] > div {
              width: min(92vw, 680px) !important;
              margin: 0.8rem auto !important;
              border-radius: 1.25rem !important;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_dremio_source_picker_no_email():
    st.markdown("#### Dremio")
    st.caption("Adicione uma ou mais views ao ambiente analítico desta conversa.")
    effective_pat = st.session_state.get("dremio_pat")
    if not effective_pat:
        st.info("Desbloqueie o app com seu PAT do Dremio para carregar as fontes.")
        return

    if st.button("Buscar catálogos", use_container_width=True, key="modal_buscar_catalogos"):
        try:
            engine = app.base_app._create_dremio_engine(effective_pat)
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
        selected_catalog = st.selectbox("Catálogo/Workspace", catalogs, key="modal_dremio_catalog_select")
        if selected_catalog != st.session_state.get("dremio_selected_catalog"):
            st.session_state.dremio_selected_catalog = selected_catalog
            st.session_state.dremio_containers = []
            st.session_state.dremio_views = []
            st.session_state.dremio_selected_container = None
            st.session_state.dremio_selected_view = None
        if st.button("Listar pastas", disabled=not selected_catalog, key="modal_listar_pastas"):
            try:
                engine = app.base_app._create_dremio_engine(effective_pat)
                st.session_state.dremio_containers = engine.list_child_containers(selected_catalog)
                st.session_state.dremio_views = []
                if not st.session_state.dremio_containers:
                    st.warning("Não encontrei pastas nesse catálogo.")
            except Exception as exc:
                st.error(f"Falha ao listar pastas: {exc}")

    containers = st.session_state.get("dremio_containers", [])
    if containers:
        container_map = app.base_app._unique_display_map(containers, levels=1)
        container_options = ["(usar catálogo inteiro)"] + list(container_map.keys())
        selected_container_label = st.selectbox("Pasta", container_options, key="modal_dremio_container_select")
        selected_container = selected_catalog if selected_container_label == "(usar catálogo inteiro)" else container_map[selected_container_label]
        if selected_container != st.session_state.get("dremio_selected_container"):
            st.session_state.dremio_selected_container = selected_container
            st.session_state.dremio_views = []
            st.session_state.dremio_selected_view = None
        if st.button("Carregar views da pasta", disabled=not selected_container, key="modal_carregar_views"):
            try:
                engine = app.base_app._create_dremio_engine(effective_pat)
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
        filtered_views = [
            view for view in views
            if not query or query in app.base_app._view_label(view).lower() or query in view.full_path.lower()
        ]
        if filtered_views:
            view_map = app.base_app._unique_view_display_map(filtered_views)
            selected_view_label = st.selectbox("Views encontradas", list(view_map.keys()), key="modal_dremio_view_select")
            selected_view_obj = view_map[selected_view_label]
            selected_view = selected_view_obj.full_path
            st.session_state.dremio_selected_view = selected_view
            st.caption(f"Selecionada: `{app.base_app._view_label(selected_view_obj)}`")
            st.caption(f"Caminho técnico: `{selected_view}`")
            if st.button("Adicionar view à análise", type="secondary", use_container_width=True, key="modal_add_view", disabled=not selected_view):
                app.add_dremio_source(selected_view, app.base_app._view_label(selected_view_obj))
        else:
            st.info("Nenhuma view encontrada com esse filtro.")
        st.caption(f"{len(filtered_views)} de {len(views)} view(s) encontrada(s).")


def render_source_manager_content_compact():
    app.phase_state()
    tab_dremio, tab_planilha, tab_conectadas, tab_relacionamentos = st.tabs([
        "Dremio",
        "Planilha",
        "Conectadas",
        "Relações",
    ])
    with tab_dremio:
        render_dremio_source_picker_no_email()
    with tab_planilha:
        st.caption("Planilhas continuam disponíveis aqui. A multi-view Dremio é o foco desta fase.")
        app.base_app.setup_spreadsheet_ui()
    with tab_conectadas:
        app.render_selected_sources()
    with tab_relacionamentos:
        app.render_relationship_manager()


def render_auth_gate_refined() -> bool:
    if st.session_state.get("authenticated"):
        return True
    inject_auth_visual_refinement()
    return _ORIGINAL_AUTH_GATE()


app.render_auth_gate = render_auth_gate_refined
app.base_app.render_auth_gate = render_auth_gate_refined
app.render_dremio_source_picker = render_dremio_source_picker_no_email
app.render_source_manager_content = render_source_manager_content_compact

if __name__ == "__main__":
    inject_mobile_visual_refinement()
    app.main()
