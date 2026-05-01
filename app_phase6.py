import streamlit as st
import streamlit.components.v1 as components

import app_phase5 as phase5

entry = phase5.entry


def force_browser_title():
    components.html(
        f"<script>window.parent.document.title = {entry.APP_NAME!r};</script>",
        height=0,
    )


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
    entry.base_app.update_conversation_state(
        active_sources=[],
        dremio_sources=[],
        relationships=[],
        data_profiles={},
        selected_dremio_view="",
    )


def rename_conversation(conversation_id: str, title: str):
    title = (title or "").strip()
    if not title:
        st.warning("Informe um nome para a conversa.")
        return
    store = entry.base_app.memory()
    if not store:
        st.error("Memória persistente indisponível.")
        return
    store.update_conversation(conversation_id, title=title)
    entry.base_app.refresh_conversations()
    st.session_state.editing_conversation_id = None
    st.session_state.editing_conversation_title = ""


def delete_conversation(conversation_id: str):
    store = entry.base_app.memory()
    if not store:
        st.error("Memória persistente indisponível.")
        return
    store.update_conversation(conversation_id, status="deleted")
    if st.session_state.get("conversation_id") == conversation_id:
        st.session_state.conversation_id = None
        st.session_state.messages = []
        if st.session_state.get("agent"):
            st.session_state.agent.load_history([])
    entry.base_app.refresh_conversations()


def render_conversation_sidebar_with_actions():
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
                    rename_conversation(conv_id, new_title)
                    st.rerun()
            with col_cancel:
                if st.button("Cancelar", key=f"cancel_title_{conv_id}", use_container_width=True):
                    st.session_state.editing_conversation_id = None
                    st.session_state.editing_conversation_title = ""
                    st.rerun()
            continue

        if st.session_state.delete_conversation_id == conv_id:
            st.warning(f"Apagar: {title[:38]}?")
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

        col_open, col_edit, col_delete = st.columns([6, 1, 1])
        with col_open:
            label = f"{'✅ ' if is_current else ''}{title[:48]}"
            if st.button(label, key=f"open_conversation_{conv_id}", use_container_width=True, disabled=is_current):
                entry.base_app.load_conversation(conv_id)
                st.rerun()
        with col_edit:
            if st.button("✏️", key=f"edit_conversation_{conv_id}", help="Renomear conversa"):
                st.session_state.editing_conversation_id = conv_id
                st.session_state.editing_conversation_title = title
                st.rerun()
        with col_delete:
            if st.button("🗑️", key=f"delete_conversation_{conv_id}", help="Apagar conversa"):
                st.session_state.delete_conversation_id = conv_id
                st.rerun()

    if st.session_state.get("memory_error"):
        st.caption("Firestore indisponível. Persistência real será retomada quando a API estiver ativa.")


def render_selected_sources_with_reset():
    phase5.phase3.phase3_state()
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
                entry.remove_dremio_source(src["path"])
                st.rerun()

    if st.button("Conectar fontes selecionadas", type="primary", use_container_width=True, key="connect_selected_sources"):
        if entry.connect_dremio_sources():
            st.session_state.show_source_manager = False
            st.rerun()


def render_sidebar_without_session_block():
    force_browser_title()
    entry.inject_sidebar_compact_css()
    phase5.phase3.phase3_state()
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
            render_conversation_sidebar_with_actions()


def render_auth_gate_with_title() -> bool:
    force_browser_title()
    return phase5.phase4.render_auth_gate_theme_aware()


def render_chat_with_title():
    force_browser_title()
    return entry.render_chat_with_history_first()


entry.render_selected_sources = render_selected_sources_with_reset
entry.base_app.render_sidebar = render_sidebar_without_session_block
entry.base_app.render_conversation_sidebar = render_conversation_sidebar_with_actions
entry.base_app.render_auth_gate = render_auth_gate_with_title
entry.base_app.render_chat = render_chat_with_title

if __name__ == "__main__":
    entry.base_app.main()
