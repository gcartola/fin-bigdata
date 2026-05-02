import streamlit as st

import app_phase8 as phase8

entry = phase8.entry
phase6 = phase8.phase6


def short_title(title: str, max_chars: int = 28) -> str:
    title = " ".join((title or "Conversa sem título").split())
    return title if len(title) <= max_chars else title[: max_chars - 3].rstrip() + "..."


def inject_conversation_sidebar_css():
    st.markdown(
        """
        <style>
          [data-testid="stSidebar"] button p {
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
          }

          [data-testid="stSidebar"] div[data-testid="stHorizontalBlock"] {
            gap: 0.25rem;
          }

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


def render_conversation_sidebar_compact():
    inject_conversation_sidebar_css()
    st.markdown("### Conversas")
    st.caption("As conversas são criadas automaticamente na primeira pergunta.")
    if st.button("Nova conversa", use_container_width=True):
        entry.base_app.new_conversation()

    entry.base_app.refresh_conversations()
    conversations = st.session_state.get("saved_conversations", [])
    if not conversations:
        if st.session_state.get("memory_error"):
            st.caption("Memória persistente indisponível; a conversa atual fica só nesta sessão.")
        else:
            st.caption("Nenhuma conversa iniciada ainda.")
        return

    current = st.session_state.get("conversation_id")
    if "editing_conversation_id" not in st.session_state:
        st.session_state.editing_conversation_id = None
    if "editing_conversation_title" not in st.session_state:
        st.session_state.editing_conversation_title = ""
    if "delete_conversation_id" not in st.session_state:
        st.session_state.delete_conversation_id = None

    for conv in conversations:
        conv_id = conv.get("id")
        title = conv.get("title") or "Conversa sem título"
        is_current = conv_id == current

        if st.session_state.editing_conversation_id == conv_id:
            new_title = st.text_input(
                "Nome da conversa",
                value=st.session_state.editing_conversation_title or title,
                key=f"edit_title_{conv_id}",
                label_visibility="collapsed",
            )
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("Salvar", key=f"save_title_{conv_id}", use_container_width=True):
                    phase6.rename_conversation(conv_id, new_title)
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
                    phase6.delete_conversation(conv_id)
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
            if st.button(
                label,
                key=f"open_conversation_{conv_id}",
                use_container_width=True,
                disabled=is_current,
                help=title,
            ):
                entry.base_app.load_conversation(conv_id)
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


def render_sidebar_refined():
    phase6.force_browser_title()
    entry.inject_sidebar_compact_css()
    inject_conversation_sidebar_css()
    phase6.phase5.phase3.phase3_state()
    _, _, model = entry.base_app.get_vertex_config()
    with st.sidebar:
        st.title(entry.APP_NAME)
        st.caption("Análises de BigDados")
        st.caption(f"Modelo: `{model}`")

        if st.session_state.get("authenticated"):
            st.caption(f"Usuário: `{st.session_state.get('user_email')}`")
            if st.button("Trocar PAT / sair", use_container_width=True):
                entry.base_app.reset_workspace(keep_auth=False)
                st.session_state.active_dremio_sources = []
                st.session_state.source_relationships = []
                st.session_state.source_columns_by_path = {}
                st.session_state.relationship_suggestions = []
                st.session_state.source_data_profiles = {}
                st.rerun()
        else:
            st.warning("App bloqueado. Informe seu PAT para liberar o agente.")

        st.divider()
        entry.render_source_summary_sidebar()

        if st.session_state.get("authenticated"):
            st.divider()
            render_conversation_sidebar_compact()


entry.base_app.render_sidebar = render_sidebar_refined
entry.base_app.render_conversation_sidebar = render_conversation_sidebar_compact
entry.base_app.render_chat = phase8.render_chat_result_first
entry.base_app.render_download_buttons = phase8.render_query_result_block

if __name__ == "__main__":
    entry.base_app.main()
