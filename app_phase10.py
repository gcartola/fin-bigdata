import streamlit as st

# Fonte da verdade do título/favicon: roda antes de importar a cadeia antiga do app.
st.set_page_config(page_title="BigDados", page_icon="📊", layout="wide")

# O app.py legado também chama set_page_config ao ser importado. Depois que a
# configuração correta foi aplicada acima, neutralizamos novas chamadas para
# evitar conflito e parar a alternância de título/ícone no browser.
st.set_page_config = lambda *args, **kwargs: None

import pandas as pd

import app_phase9 as phase9

entry = phase9.entry
phase8 = phase9.phase8
phase6 = phase9.phase6

# Remove hacks de document.title. O título agora vem do set_page_config acima.
phase6.force_browser_title = lambda: None


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


def query_result_payload(result, max_rows: int = 100) -> dict | None:
    if not result or not getattr(result, "rows", None):
        return None
    rows = []
    for row in result.rows[:max_rows]:
        rows.append([scalar_for_firestore(value) for value in row])
    return {
        "columns": list(result.columns),
        "rows": rows,
        "sample_row_count": len(rows),
        "row_count": int(result.row_count or len(rows)),
        "sql_executed": getattr(result, "sql_executed", None),
        "execution_time_ms": getattr(result, "execution_time_ms", None),
    }


def dataframe_from_payload(payload: dict) -> pd.DataFrame:
    return pd.DataFrame(payload.get("rows") or [], columns=payload.get("columns") or [])


def render_copy_sql_button(sql: str, key: str):
    return phase8.render_copy_sql_button(sql, key)


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


def render_live_result_block(result=None):
    agent = st.session_state.get("agent")
    result = result or (getattr(agent, "last_query_result", None) if agent else None)
    payload = query_result_payload(result, max_rows=500)
    if not payload:
        return
    key = f"live_{len(st.session_state.get('messages', []))}_{abs(hash(payload.get('sql_executed') or ''))}"
    render_payload_result_block(payload, key=key)


def load_conversation_with_result_blocks(conversation_id: str):
    store = entry.base_app.memory()
    messages = []
    if store and not str(conversation_id).startswith("local-"):
        messages = store.get_messages(conversation_id, limit=50)

    hydrated = []
    for m in messages:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        item = {"role": role, "content": m.get("content", "")}
        query_result = m.get("query_result")
        if query_result:
            item["query_result"] = query_result
        hydrated.append(item)

    st.session_state.conversation_id = conversation_id
    st.session_state.messages = hydrated
    if st.session_state.get("agent"):
        # O histórico textual vai para o modelo; o bloco estruturado fica só na UI.
        st.session_state.agent.load_history(st.session_state.messages)

    try:
        entry.hydrate_workspace_from_conversation(conversation_id)
    except Exception:
        pass


def render_messages_with_persisted_results():
    messages = st.session_state.get("messages", [])
    for index, msg in enumerate(messages):
        with st.chat_message(msg["role"]):
            if msg.get("role") == "assistant" and msg.get("query_result"):
                render_payload_result_block(msg["query_result"], key=f"msg_{index}")
            st.markdown(msg.get("content", ""))


def render_chat_persistent_results():
    st.title(f"📊 {entry.home_title()}")
    st.caption(entry.APP_CAPTION)

    if st.session_state.get("conversation_id"):
        st.caption(f"Conversa: `{st.session_state.conversation_id}`")

    render_messages_with_persisted_results()

    if not st.session_state.agent:
        st.info(entry.NO_SOURCE_MESSAGE)
        return

    entry.apply_agent_workspace_context()
    user_input = st.chat_input("Pergunte algo sobre os dados...")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    entry.base_app.append_persistent_message("user", user_input)

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
        response = phase8.clean_agent_response_for_structured_result(raw_response) if result else raw_response
        payload = query_result_payload(result, max_rows=500)
        if payload:
            render_payload_result_block(payload, key="new_result")
        st.markdown(response)

    result = getattr(st.session_state.agent, "last_query_result", None)
    payload = query_result_payload(result, max_rows=500)
    response = phase8.clean_agent_response_for_structured_result(raw_response) if result else raw_response

    assistant_message = {"role": "assistant", "content": response}
    if payload:
        assistant_message["query_result"] = payload
    st.session_state.messages.append(assistant_message)

    entry.base_app.append_persistent_message(
        "assistant",
        response,
        sql=getattr(result, "sql_executed", None),
        query_result_summary=entry.base_app.result_summary(result),
        query_result=payload,
    )

    if result:
        entry.base_app.update_conversation_state(
            last_query_sql=result.sql_executed,
            last_result_summary=entry.base_app.result_summary(result),
        )

    st.rerun()


entry.base_app.load_conversation = load_conversation_with_result_blocks
entry.base_app.render_chat = render_chat_persistent_results
entry.base_app.render_download_buttons = render_live_result_block

if __name__ == "__main__":
    entry.base_app.main()
