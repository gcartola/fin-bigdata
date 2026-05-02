import streamlit as st

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


def render_auth_gate_refined() -> bool:
    inject_auth_visual_refinement()
    return _ORIGINAL_AUTH_GATE()


app.render_auth_gate = render_auth_gate_refined
app.base_app.render_auth_gate = render_auth_gate_refined

if __name__ == "__main__":
    app.main()
