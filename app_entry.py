import streamlit as st

import app as base_app


def render_chat_with_history_first():
    st.title("📊 Fin BigData")
    st.caption("Bancada analítica assistida por Gemini. O agente consulta dados estruturados, não arquivo bruto no prompt.")

    if st.session_state.get("conversation_id"):
        st.caption(f"Conversa: `{st.session_state.conversation_id}`")

    # Histórico persistido é parte do workspace e deve aparecer mesmo antes de
    # reconectar uma fonte/engine. Antes o app retornava cedo quando não havia
    # agent ativo, deixando a conversa carregada em branco após logout/login.
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if not st.session_state.agent:
        st.info("Escolha uma fonte de dados na barra lateral para continuar esta conversa com o agente.")
        return

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

    # A sidebar é renderizada antes do chat. Força atualização para a conversa
    # recém-criada/atualizada aparecer imediatamente no menu lateral.
    st.rerun()


base_app.render_chat = render_chat_with_history_first

if __name__ == "__main__":
    base_app.main()
