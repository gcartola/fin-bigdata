import streamlit as st

import app_phase4 as phase4

phase3 = phase4.phase3
entry = phase4.entry


def safe_workspace_context() -> str:
    sources = st.session_state.get("active_dremio_sources", [])
    relationships = st.session_state.get("source_relationships", [])
    suggestions = st.session_state.get("relationship_suggestions", [])[:5]
    profiles = st.session_state.get("source_data_profiles", {})

    if not sources and not relationships and not suggestions and not profiles:
        return ""

    lines = [
        "\n\nCONTEXTO DO WORKSPACE BIGDADOS:",
        "As fontes abaixo foram selecionadas pelo usuário para esta conversa.",
    ]

    if sources:
        lines.append("\nFontes ativas:")
        for src in sources:
            lines.append(
                f"- alias `{src.get('alias')}` | nome `{src.get('name')}` | path {src.get('path')}"
            )

    if relationships:
        lines.append("\nRelacionamentos conhecidos definidos pelo usuário:")
        for rel in relationships:
            lines.append(
                f"- `{rel.get('left_name')}`.`{rel.get('left_column')}` "
                f"= `{rel.get('right_name')}`.`{rel.get('right_column')}` "
                f"(confiança: {rel.get('confidence', 'manual')}, score: {rel.get('score', 'manual')})"
            )
        lines.append(
            "\nQuando o usuário pedir análise cruzada entre fontes, use esses relacionamentos "
            "como chaves preferenciais. Ainda assim, descreva e amostre as tabelas antes de montar SQL. "
            "Se a junção puder duplicar linhas, avise e prefira validar contagens/amostras antes de concluir."
        )

    if suggestions:
        lines.append("\nSugestões automáticas recentes de relacionamento:")
        for item in suggestions:
            lines.append(
                f"- {item.get('left_name')}.{item.get('left_column')} = "
                f"{item.get('right_name')}.{item.get('right_column')} "
                f"score={item.get('score')} confiança={item.get('confidence')}"
            )

    if profiles:
        lines.append("\nPerfis de dados calculados:")
        for profile in profiles.values():
            lines.append(
                f"- {entry.source_name_from_path(profile.get('path', ''))}.{profile.get('column')}: "
                f"linhas={profile.get('total_linhas')}, preenchidas={profile.get('valores_preenchidos')}, "
                f"distintas={profile.get('valores_distintos')}"
            )

    if suggestions or profiles:
        lines.append(
            "\nUse score/perfil como apoio. Não trate sugestão automática como relacionamento confirmado "
            "se ela não estiver em Relacionamentos conhecidos."
        )

    return "\n".join(lines)


def safe_hydrate_workspace_from_conversation(conversation_id: str):
    store = entry.base_app.memory()
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
    entry.apply_agent_workspace_context()


def safe_load_conversation(conversation_id: str):
    entry.base_app._original_load_conversation(conversation_id)
    safe_hydrate_workspace_from_conversation(conversation_id)


entry.build_agent_context = safe_workspace_context
entry.hydrate_workspace_from_conversation = safe_hydrate_workspace_from_conversation
entry.base_app.load_conversation = safe_load_conversation

if __name__ == "__main__":
    entry.base_app.main()
