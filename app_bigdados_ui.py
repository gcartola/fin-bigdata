import streamlit as st

import app_bigdados as app

_ORIGINAL_AUTH_GATE = app.render_auth_gate


def inject_auth_visual_refinement():
    st.markdown(
        """
        <style>
          .bigdados-auth-shell {
            width: min(448px, 92vw) !important;
            max-width: 448px !important;
            margin-top: 8vh !important;
            gap: 12px !important;
          }

          .bigdados-login-logo {
            width: min(180px, 34vw) !important;
            max-height: 138px !important;
            margin-bottom: 2px !important;
          }

          .bigdados-auth-card {
            width: 100% !important;
            box-sizing: border-box !important;
            padding: 20px 22px !important;
            background: color-mix(in srgb, var(--secondary-background-color) 74%, transparent) !important;
            border-color: color-mix(in srgb, var(--text-color) 12%, transparent) !important;
          }

          .bigdados-auth-title {
            font-size: 23px !important;
          }

          .bigdados-auth-subtitle {
            font-size: 13px !important;
            font-weight: 560 !important;
            color: color-mix(in srgb, var(--text-color) 80%, transparent) !important;
          }

          main div[data-testid="stTextInput"],
          main div[data-testid="stButton"] {
            width: min(448px, 92vw) !important;
            max-width: 448px !important;
            margin-left: auto !important;
            margin-right: auto !important;
          }

          main .stAlert {
            width: min(448px, 92vw) !important;
            max-width: 448px !important;
            margin-left: auto !important;
            margin-right: auto !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_auth_gate_refined() -> bool:
    inject_auth_visual_refinement()
    return _ORIGINAL_AUTH_GATE()


app.render_auth_gate = render_auth_gate_refined
app.base_app.render_auth_gate = render_auth_gate_refined

if __name__ == "__main__":
    app.main()
