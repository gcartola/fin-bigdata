from io import BytesIO

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import app_phase6 as phase6

entry = phase6.entry


def phase7_state():
    if "show_save_table_dialog" not in st.session_state:
        st.session_state.show_save_table_dialog = False
    if "saved_table_drafts" not in st.session_state:
        st.session_state.saved_table_drafts = []


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


def open_save_table_dialog():
    st.session_state.show_save_table_dialog = True


def render_save_table_dialog(result):
    phase7_state()
    if not st.session_state.get("show_save_table_dialog"):
        return

    def save_table_form():
        st.caption("Nesta etapa o BigDados salva um rascunho local do artefato. A persistência no Firestore entra na Fase 4.2.")
        default_name = f"Tabela salva · {pd.Timestamp.now().strftime('%d/%m %H:%M')}"
        name = st.text_input("Nome da tabela", value=default_name)
        description = st.text_area("Descrição opcional", value="")
        col_cancel, col_save = st.columns(2)
        with col_cancel:
            if st.button("Cancelar", use_container_width=True):
                st.session_state.show_save_table_dialog = False
                st.rerun()
        with col_save:
            if st.button("Salvar tabela", type="primary", use_container_width=True):
                sample_df = result_dataframe(result).head(20)
                st.session_state.saved_table_drafts.append({
                    "name": name.strip() or default_name,
                    "description": description.strip(),
                    "sql": getattr(result, "sql_executed", None),
                    "columns": list(result.columns),
                    "sample_rows": sample_df.to_dict(orient="records"),
                    "row_count": result.row_count,
                    "created_at": pd.Timestamp.now().isoformat(),
                })
                st.session_state.show_save_table_dialog = False
                st.success("Tabela salva como rascunho desta sessão.")
                st.rerun()

    if hasattr(st, "dialog"):
        @st.dialog("Salvar tabela", width="large")
        def dialog():
            save_table_form()
        dialog()
    else:
        with st.expander("Salvar tabela", expanded=True):
            save_table_form()


def render_query_result_block(result=None):
    phase7_state()
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

        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="resultado")

        col_csv, col_excel, col_save = st.columns(3)
        with col_csv:
            st.download_button(
                "Baixar CSV",
                csv_bytes,
                "resultado_bigdados.csv",
                "text/csv",
                use_container_width=True,
                key=f"rich_download_csv_{key}",
            )
        with col_excel:
            st.download_button(
                "Baixar Excel",
                excel_buffer.getvalue(),
                "resultado_bigdados.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"rich_download_excel_{key}",
            )
        with col_save:
            if st.button("Salvar tabela", use_container_width=True, key=f"save_table_{key}"):
                open_save_table_dialog()
                st.rerun()

        st.dataframe(df, use_container_width=True, hide_index=True)

        with st.expander("SQL gerado", expanded=False):
            if sql:
                render_copy_sql_button(sql, key)
                st.code(sql, language="sql")
            else:
                st.caption("Nenhum SQL registrado para este resultado.")

    render_save_table_dialog(result)


def render_chat_with_analytical_block():
    phase6.force_browser_title()
    st.title(f"📊 {entry.home_title()}")
    st.caption(entry.APP_CAPTION)

    if st.session_state.get("conversation_id"):
        st.caption(f"Conversa: `{st.session_state.conversation_id}`")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if not st.session_state.agent:
        st.info(entry.NO_SOURCE_MESSAGE)
        return

    entry.apply_agent_workspace_context()
    user_input = st.chat_input("Pergunte algo sobre os dados...")
    if not user_input:
        render_query_result_block()
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
            response = st.session_state.agent.chat(user_input, progress_callback=update_status)
        except Exception as exc:
            response = f"Erro ao processar pergunta: {exc}"
            update_status("❌ Erro ao processar pergunta")

        status_box.empty()
        st.markdown(response)

    result = getattr(st.session_state.agent, "last_query_result", None)
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


entry.base_app.render_chat = render_chat_with_analytical_block
entry.base_app.render_download_buttons = render_query_result_block

if __name__ == "__main__":
    entry.base_app.main()
