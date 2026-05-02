import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import app_phase7 as phase7

entry = phase7.entry
phase6 = phase7.phase6


def result_dataframe(result) -> pd.DataFrame:
    return pd.DataFrame(result.rows, columns=result.columns)


def result_key(result) -> str:
    sql = getattr(result, "sql_executed", "") or ""
    return f"{len(st.session_state.get('messages', []))}_{getattr(result, 'row_count', 0)}_{abs(hash(sql))}"


def render_copy_sql_button(sql: str, key: str):
    if not sql:
        return
    components.html(
        f"""
        <button id="copy-sql-{key}" style="
          width: 100%;
          border: 1px solid rgba(148, 163, 184, .35);
          border-radius: 10px;
          padding: 9px 12px;
          background: transparent;
          color: inherit;
          font-weight: 650;
          cursor: pointer;
        ">Copiar SQL</button>
        <script>
          const btn = document.getElementById('copy-sql-{key}');
          btn.onclick = async () => {{
            try {{
              await navigator.clipboard.writeText({sql!r});
              btn.innerText = 'SQL copiado';
              setTimeout(() => btn.innerText = 'Copiar SQL', 1600);
            }} catch (err) {{
              btn.innerText = 'Não consegui copiar';
              setTimeout(() => btn.innerText = 'Copiar SQL', 1600);
            }}
          }};
        </script>
        """,
        height=46,
    )


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

    # Remove blocos SQL antigos que o agente escrevia na resposta textual.
    cleaned = re.sub(
        r"(?is)\n*\*{0,2}\s*SQL\s+(utilizado|gerado|usado|que usei)\s*:?\s*\*{0,2}\s*```sql.*?```",
        "\n",
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)\n*\*{0,2}\s*SQL\s+(utilizado|gerado|usado|que usei)\s*:?\s*\*{0,2}\s*```.*?```",
        "\n",
        cleaned,
    )

    # Remove qualquer fenced code SQL restante. O SQL oficial agora fica no expander.
    cleaned = re.sub(r"(?is)```sql.*?```", "\n", cleaned)

    # Remove tabelas markdown duplicadas. A tabela oficial agora é o dataframe do bloco analítico.
    cleaned = strip_markdown_tables(cleaned)

    # Remove chamadas introdutórias que só faziam sentido antes da tabela.
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

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned or "Analisei o resultado acima."


def render_query_result_block(result=None):
    agent = st.session_state.get("agent")
    result = result or (getattr(agent, "last_query_result", None) if agent else None)
    if not result or not getattr(result, "rows", None):
        return

    df = result_dataframe(result)
    sql = getattr(result, "sql_executed", None) or ""
    key = result_key(result)

    st.markdown("### Resultado da consulta")
    with st.container(border=True):
        st.caption(
            f"{len(df):,} linha(s) retornada(s) · {len(df.columns)} coluna(s)"
            + (f" · {getattr(result, 'execution_time_ms', None)}ms" if getattr(result, "execution_time_ms", None) else "")
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

        with st.expander("SQL gerado", expanded=False):
            if sql:
                render_copy_sql_button(sql, key)
                st.code(sql, language="sql")
            else:
                st.caption("Nenhum SQL registrado para este resultado.")


def should_insert_current_result_before_last_assistant(index: int, messages: list[dict]) -> bool:
    if not messages or index != len(messages) - 1:
        return False
    if messages[index].get("role") != "assistant":
        return False
    agent = st.session_state.get("agent")
    result = getattr(agent, "last_query_result", None) if agent else None
    return bool(result and getattr(result, "rows", None))


def render_messages_with_result_first():
    messages = st.session_state.get("messages", [])
    for index, msg in enumerate(messages):
        with st.chat_message(msg["role"]):
            if should_insert_current_result_before_last_assistant(index, messages):
                render_query_result_block()
            st.markdown(msg["content"])


def render_chat_result_first():
    phase6.force_browser_title()
    st.title(f"📊 {entry.home_title()}")
    st.caption(entry.APP_CAPTION)

    if st.session_state.get("conversation_id"):
        st.caption(f"Conversa: `{st.session_state.conversation_id}`")

    render_messages_with_result_first()

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
        response = clean_agent_response_for_structured_result(raw_response) if result else raw_response
        if result:
            render_query_result_block(result)
        st.markdown(response)

    result = getattr(st.session_state.agent, "last_query_result", None)
    response = clean_agent_response_for_structured_result(raw_response) if result else raw_response
    st.session_state.messages.append({"role": "assistant", "content": response})
    entry.base_app.append_persistent_message(
        "assistant",
        response,
        sql=getattr(result, "sql_executed", None),
        query_result_summary=entry.base_app.result_summary(result),
    )

    if result:
        entry.base_app.update_conversation_state(
            last_query_sql=result.sql_executed,
            last_result_summary=entry.base_app.result_summary(result),
        )

    st.rerun()


entry.base_app.render_chat = render_chat_result_first
entry.base_app.render_download_buttons = render_query_result_block

if __name__ == "__main__":
    entry.base_app.main()
