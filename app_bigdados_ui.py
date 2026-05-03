import streamlit as st
import streamlit.components.v1 as components

import app_bigdados as app

_ORIGINAL_AUTH_GATE = app.render_auth_gate

AUTH_BOX_WIDTH = "min(448px, 92vw)"


def inject_auth_visual_refinement():
    st.markdown(
        f"""
        <style>
          main .block-container {{
            padding-top: 0.25rem !important;
            padding-bottom: 1rem !important;
          }}

          .bigdados-auth-shell {{
            width: {AUTH_BOX_WIDTH} !important;
            max-width: 448px !important;
            margin: 0.25vh auto 0 auto !important;
            gap: 0 !important;
            align-items: stretch !important;
          }}

          .bigdados-login-logo {{
            display: none !important;
          }}

          .bigdados-auth-card {{
            width: 100% !important;
            box-sizing: border-box !important;
            padding: 18px 22px !important;
            border-radius: 20px !important;
            background: color-mix(in srgb, var(--secondary-background-color) 70%, transparent) !important;
            border-color: color-mix(in srgb, var(--text-color) 10%, transparent) !important;
          }}

          .bigdados-auth-title {{
            font-size: 22px !important;
            margin-bottom: 8px !important;
          }}

          .bigdados-auth-subtitle {{
            font-size: 12.5px !important;
            line-height: 1.38 !important;
            font-weight: 560 !important;
            color: color-mix(in srgb, var(--text-color) 82%, transparent) !important;
          }}

          .bigdados-auth-input-wrap {{
            width: {AUTH_BOX_WIDTH} !important;
            max-width: 448px !important;
            margin: 12px auto 0 auto !important;
            padding: 0 !important;
            border: 0 !important;
            background: transparent !important;
            box-shadow: none !important;
          }}

          .bigdados-auth-input-wrap div[data-testid="stTextInput"],
          .bigdados-auth-input-wrap div[data-testid="stButton"] {{
            width: 100% !important;
            max-width: 448px !important;
            margin-left: 0 !important;
            margin-right: 0 !important;
          }}

          .bigdados-auth-input-wrap div[data-testid="stButton"] {{
            margin-top: 8px !important;
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
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_mobile_visual_refinement():
    """Ajustes finos para uso real no celular: hero mais alto, conversas compactas e modal fixo."""
    st.markdown(
        """
        <style>
          /* Sobe o hero/boas-vindas. No mobile cada vh custa ouro, sem cerimônia. */
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

          /* Sidebar: força linha única para título + lápis + lixeira, evitando o efeito sanfona do Streamlit no mobile. */
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

          /* Dialog/modal fixo: a página não sai passeando; quem rola é o conteúdo do modal. */
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
    inject_auth_visual_refinement()
    return _ORIGINAL_AUTH_GATE()


app.render_auth_gate = render_auth_gate_refined
app.base_app.render_auth_gate = render_auth_gate_refined

if __name__ == "__main__":
    inject_mobile_visual_refinement()
    hide_user_email_inside_source_manager()
    app.main()
