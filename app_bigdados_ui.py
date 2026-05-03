import streamlit as st
import streamlit.components.v1 as components

import app_bigdados as app

AUTH_BOX_WIDTH = "min(448px, 92vw)"


def inject_auth_visual_refinement():
    st.markdown(
        f"""
        <style>
          main .block-container {{
            padding-top: 0.75rem !important;
            padding-bottom: 1rem !important;
          }}

          [data-testid="stSidebar"] {{
            filter: blur(1.8px);
            opacity: 0.56;
          }}

          .bigdados-auth-shell {{
            width: {AUTH_BOX_WIDTH};
            max-width: 448px;
            margin: 1.4vh auto 0 auto;
            display: flex;
            flex-direction: column;
            gap: 10px;
            align-items: stretch;
          }}

          .bigdados-auth-card {{
            width: 100%;
            box-sizing: border-box;
            padding: 20px 22px;
            border-radius: 20px;
            border: 1px solid color-mix(in srgb, var(--text-color) 10%, transparent);
            background: color-mix(in srgb, var(--secondary-background-color) 70%, transparent);
            color: var(--text-color);
            box-shadow: 0 14px 42px rgba(0, 0, 0, 0.16);
          }}

          .bigdados-auth-title {{
            font-size: 24px;
            line-height: 1.12;
            font-weight: 850;
            letter-spacing: -0.03em;
            margin-bottom: 8px;
          }}

          .bigdados-auth-subtitle {{
            font-size: 13px;
            line-height: 1.42;
            font-weight: 560;
            color: color-mix(in srgb, var(--text-color) 82%, transparent);
          }}

          div[data-testid="stForm"] {{
            width: {AUTH_BOX_WIDTH} !important;
            max-width: 448px !important;
            margin: 14px auto 0 auto !important;
            padding: 0 !important;
            border: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
          }}

          div[data-testid="stForm"] div[data-testid="stTextInput"],
          div[data-testid="stForm"] div[data-testid="stButton"] {{
            width: 100% !important;
            max-width: 448px !important;
            margin-left: 0 !important;
            margin-right: 0 !important;
          }}

          div[data-testid="stForm"] button[kind="primary"] {{
            margin-top: 8px !important;
            border-radius: 10px !important;
          }}

          main .stAlert {{
            width: {AUTH_BOX_WIDTH} !important;
            max-width: 448px !important;
            margin: 12px auto 0 auto !important;
          }}

          main .stAlert > div {{
            width: 100% !important;
            box-sizing: border-box !important;
          }}

          @media (max-width: 700px) {{
            main .block-container {{
              padding-top: 0.25rem !important;
              padding-left: 1rem !important;
              padding-right: 1rem !important;
            }}

            .bigdados-auth-shell {{
              margin-top: 0.4rem !important;
            }}

            /* Na tela bloqueada, o menu lateral no celular só atrapalha e vira cortina. */
            [data-testid="stSidebar"] {{
              display: none !important;
            }}
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_mobile_visual_refinement():
    """Ajustes finos para uso real no celular: hero mais alto, conversas compactas e modal fixo."""
    st.markdown(
        """
        <style>
          main .block-container {
            padding-top: 0 !important;
            margin-top: 0 !important;
          }
          main h1 {
            margin-top: 0 !important;
            padding-top: 0 !important;
          }
          main h1:first-of-type {
            margin-block-start: 0 !important;
            margin-bottom: 0.55rem !important;
            line-height: 1.08 !important;
          }
          main [data-testid="stVerticalBlock"] > [style*="flex-direction: column"] {
            gap: 0.6rem !important;
          }

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
          [data-testid="stSidebar"] button {
            min-width: 0 !important;
          }
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

          div[data-testid="stDialog"],
          div[role="dialog"] {
            position: fixed !important;
            inset: 0 !important;
            overflow: hidden !important;
          }
          div[data-testid="stDialog"] > div,
          div[role="dialog"] > div {
            max-height: calc(100dvh - 2.2rem) !important;
            overflow-y: auto !important;
            overscroll-behavior: contain !important;
          }
          div[data-testid="stDialog"] section,
          div[role="dialog"] section {
            max-height: calc(100dvh - 2.2rem) !important;
            overflow-y: auto !important;
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
            div[data-testid="stDialog"] > div,
            div[role="dialog"] > div {
              width: min(92vw, 680px) !important;
              margin: 0.8rem auto !important;
              border-radius: 1.25rem !important;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hide_user_email_inside_source_manager():
    """Remove o e-mail do usuário do modal de fontes sem mexer na autenticação/sessão."""
    user_email = st.session_state.get("user_email") or ""
    components.html(
        f"""
        <script>
        const userEmail = {user_email!r};
        function hideDremioEmail() {{
          const doc = window.parent.document;
          if (!userEmail) return;
          const nodes = Array.from(doc.querySelectorAll('p, span, div, code'));
          for (const el of nodes) {{
            const txt = (el.innerText || el.textContent || '').trim();
            if (txt.includes('Usuário Dremio') || txt.includes(userEmail)) {{
              const block = el.closest('[data-testid="stCaptionContainer"], [data-testid="stMarkdownContainer"], div[data-testid="column"], div') || el;
              block.style.display = 'none';
            }}
          }}
        }}
        hideDremioEmail();
        setInterval(hideDremioEmail, 350);
        </script>
        """,
        height=0,
    )


def render_auth_gate_refined() -> bool:
    if st.session_state.get("authenticated"):
        return True

    inject_auth_visual_refinement()
    app.force_bigdados_branding()

    st.markdown(
        f"""
        <div class="bigdados-auth-shell">
          <div class="bigdados-auth-card">
            <div class="bigdados-auth-title">Desbloquear {app.APP_NAME}</div>
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
            authenticator = app.DremioPATAuthenticator(
                app.base_app.DREMIO_CLOUD_HOST,
                app.base_app.DREMIO_CLOUD_PROJECT_ID,
                is_cloud=True,
            )
            user = authenticator.authenticate(pat)
            st.session_state.authenticated = True
            st.session_state.user_email = user.email
            st.session_state.user_id = user.user_id
            st.session_state.dremio_pat = pat.strip()
            store = app.base_app.memory()
            if store:
                store.upsert_user(user.user_id, user.email)
                app.base_app.refresh_conversations()
            st.success(f"App desbloqueado para {user.email}.")
            st.rerun()
        except Exception as exc:
            st.error(f"Não consegui validar o PAT no Dremio: {exc}")

    st.info("Depois de desbloquear, escolha a fonte Dremio ou Planilha na barra lateral para iniciar o agente.")
    return False


app.render_auth_gate = render_auth_gate_refined
app.base_app.render_auth_gate = render_auth_gate_refined

if __name__ == "__main__":
    inject_mobile_visual_refinement()
    hide_user_email_inside_source_manager()
    app.main()
