import streamlit as st

import app_phase3 as phase3

entry = phase3.entry


def render_auth_gate_theme_aware() -> bool:
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
            border: 1px solid color-mix(in srgb, var(--text-color) 18%, transparent);
            background: color-mix(in srgb, var(--secondary-background-color) 92%, transparent);
            color: var(--text-color);
            box-shadow: 0 26px 90px rgba(0, 0, 0, 0.20);
          }}

          .bigdados-auth-title {{
            font-size: 30px;
            line-height: 1.16;
            font-weight: 850;
            letter-spacing: -0.03em;
            margin-bottom: 12px;
            color: var(--text-color);
          }}

          .bigdados-auth-subtitle {{
            color: color-mix(in srgb, var(--text-color) 72%, transparent);
            font-size: 15px;
            line-height: 1.55;
          }}

          div[data-testid="stForm"] {{
            max-width: 620px;
            margin: 22px auto 0 auto;
            padding: 18px 20px 14px 20px;
            border-radius: 16px;
            border: 1px solid color-mix(in srgb, var(--text-color) 18%, transparent);
            background: color-mix(in srgb, var(--secondary-background-color) 88%, transparent);
            color: var(--text-color);
            box-shadow: 0 18px 55px rgba(0, 0, 0, 0.16);
          }}

          div[data-testid="stForm"] label,
          div[data-testid="stForm"] p,
          div[data-testid="stForm"] span {{
            color: color-mix(in srgb, var(--text-color) 78%, transparent) !important;
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
        </style>

        <div class="bigdados-auth-shell">
          <div class="bigdados-auth-card">
            <div class="bigdados-auth-title">Desbloquear {entry.APP_NAME}</div>
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
            authenticator = entry.DremioPATAuthenticator(
                entry.base_app.DREMIO_CLOUD_HOST,
                entry.base_app.DREMIO_CLOUD_PROJECT_ID,
                is_cloud=True,
            )
            user = authenticator.authenticate(pat)
            st.session_state.authenticated = True
            st.session_state.user_email = user.email
            st.session_state.user_id = user.user_id
            st.session_state.dremio_pat = pat.strip()
            store = entry.base_app.memory()
            if store:
                store.upsert_user(user.user_id, user.email)
                entry.base_app.refresh_conversations()
            st.success(f"App desbloqueado para {user.email}.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não consegui validar o PAT no Dremio: {exc}")

    st.info("Depois de desbloquear, escolha a fonte Dremio ou Planilha na barra lateral para iniciar o agente.")
    return False


entry.base_app.render_auth_gate = render_auth_gate_theme_aware

if __name__ == "__main__":
    entry.base_app.main()
