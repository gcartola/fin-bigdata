import streamlit as st

import app as base_app
from auth import DremioPATAuthenticator

APP_NAME = "BigDados"
APP_CAPTION = "Bancada analítica assistida por Gemini. O agente consulta dados estruturados, não arquivo bruto no prompt."


def render_sidebar_bigdados():
    _, _, model = base_app.get_vertex_config()
    with st.sidebar:
        st.title(APP_NAME)
        st.caption("Análises de BigData")
        st.markdown("### Agente")
        st.write(f"Modelo: `{model}`")
        if st.session_state.get("authenticated"):
            st.success("App desbloqueado")
            st.caption(f"Usuário: `{st.session_state.get('user_email')}`")
            if st.button("Trocar PAT / sair"):
                base_app.reset_workspace(keep_auth=False)
                st.rerun()
        else:
            st.warning("App bloqueado. Informe seu PAT para liberar o agente.")
        st.divider()
        base_app.setup_dremio_ui()
        st.divider()
        base_app.setup_spreadsheet_ui()
        st.divider()
        base_app.render_relationship_ui()
        st.divider()
        st.markdown("### Estado")
        if st.session_state.engine:
            st.success(st.session_state.engine.engine_name)
            for item in st.session_state.loaded_files:
                st.caption(item)
        else:
            st.warning("Nenhuma engine ativa.")
        if st.button("Resetar sessão"):
            base_app.reset_workspace(keep_auth=True)
            st.rerun()
        if st.session_state.get("authenticated"):
            st.divider()
            base_app.render_conversation_sidebar()


def render_auth_gate_bigdados() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        f"""
        <style>
          [data-testid="stSidebar"] {{
            filter: blur(1.8px);
            opacity: 0.56;
          }}

          .bigdados-auth-shell {{
            max-width: 620px;
            margin: 9vh auto 0 auto;
            display: flex;
            flex-direction: column;
            gap: 22px;
          }}

          .bigdados-auth-card {{
            padding: 30px 34px;
            border-radius: 24px;
            border: 1px solid rgba(148, 163, 184, 0.28);
            background: rgba(255, 255, 255, 0.94);
            color: #0f172a;
            box-shadow: 0 26px 90px rgba(15, 23, 42, 0.16);
          }}

          .bigdados-auth-title {{
            font-size: 30px;
            line-height: 1.16;
            font-weight: 850;
            letter-spacing: -0.03em;
            margin-bottom: 12px;
          }}

          .bigdados-auth-subtitle {{
            color: #475569;
            font-size: 15px;
            line-height: 1.55;
          }}

          div[data-testid="stForm"] {{
            max-width: 620px;
            margin: 22px auto 0 auto;
            padding: 18px 20px 14px 20px;
            border-radius: 16px;
            border: 1px solid rgba(148, 163, 184, 0.34);
            background: rgba(255, 255, 255, 0.88);
            box-shadow: 0 18px 50px rgba(15, 23, 42, 0.08);
          }}

          div[data-testid="stForm"] button[kind="primary"] {{
            border-radius: 10px;
            margin-top: 8px;
          }}

          div[data-testid="stForm"] input {{
            border-radius: 10px;
          }}

          .stAlert {{
            max-width: 620px;
            margin-left: auto;
            margin-right: auto;
          }}

          @media (prefers-color-scheme: dark) {{
            .bigdados-auth-card {{
              background: rgba(15, 23, 42, 0.88);
              color: #f8fafc;
              border-color: rgba(148, 163, 184, 0.24);
              box-shadow: 0 28px 90px rgba(0, 0, 0, 0.38);
            }}
            .bigdados-auth-subtitle {{ color: #cbd5e1; }}
            div[data-testid="stForm"] {{
              background: rgba(15, 23, 42, 0.72);
              border-color: rgba(148, 163, 184, 0.24);
              box-shadow: 0 18px 60px rgba(0, 0, 0, 0.28);
            }}
          }}
        </style>

        <div class="bigdados-auth-shell">
          <div class="bigdados-auth-card">
            <div class="bigdados-auth-title">Desbloquear {APP_NAME}</div>
            <div class="bigdados-auth-subtitle">
              Use seu PAT do Dremio para validar permissões e identificar seu e-mail corporativo.
              O token fica somente em memória nesta sessão.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("dremio_pat_unlock_form"):
        pat = st.text_input(
            "Personal Access Token do Dremio",
            value="",
            type="password",
            placeholder="Cole aqui o seu PAT do Dremio",
        )
        submitted = st.form_submit_button("Desbloquear app", type="primary", use_container_width=True)

    if submitted:
        try:
            authenticator = DremioPATAuthenticator(
                base_app.DREMIO_CLOUD_HOST,
                base_app.DREMIO_CLOUD_PROJECT_ID,
                is_cloud=True,
            )
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
    st.title(f"📊 {APP_NAME}")
    st.caption(APP_CAPTION)

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


base_app.render_sidebar = render_sidebar_bigdados
base_app.render_auth_gate = render_auth_gate_bigdados
base_app.render_chat = render_chat_with_history_first

if __name__ == "__main__":
    base_app.main()
