import streamlit as st

import app_bigdados as app

_ORIGINAL_AUTH_GATE = app.render_auth_gate

AUTH_BOX_WIDTH = "min(448px, 92vw)"


def inject_auth_visual_refinement():
    st.markdown(
        f"""
        <style>
          main .block-container {{
            padding-top: 0.75rem !important;
            padding-bottom: 1rem !important;
          }}

          .bigdados-auth-shell {{
            width: {AUTH_BOX_WIDTH} !important;
            max-width: 448px !important;
            margin: 0.8rem auto 0 auto !important;
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
    """Ajustes finos para uso real no celular, sem esconder sidebar nem conteúdo central."""
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


def render_auth_gate_refined() -> bool:
    if st.session_state.get("authenticated"):
        return True
    inject_auth_visual_refinement()
    return _ORIGINAL_AUTH_GATE()


app.render_auth_gate = render_auth_gate_refined
app.base_app.render_auth_gate = render_auth_gate_refined

if __name__ == "__main__":
    inject_mobile_visual_refinement()
    app.main()
