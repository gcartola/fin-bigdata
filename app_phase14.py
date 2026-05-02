import streamlit as st

st.set_page_config(page_title="BigDados", page_icon="🎲", layout="wide")
st.set_page_config = lambda *args, **kwargs: None

import streamlit.components.v1 as components

# Volta para a base estável da fase 12 e aplica apenas o ajuste seguro da tela inicial.
# A fase 13 quebrou o form do Streamlit; aqui removemos st.form e usamos botão simples.
import app_phase12 as phase12

entry = phase12.entry
phase10 = phase12.phase10

BIGDADOS_ICON_BASE64 = phase12.BIGDADOS_FAVICON_PNG_BASE64


def force_bigdados_branding():
    components.html(
        f"""
        <script>
        const title = "BigDados";
        const href = "data:image/png;base64,{BIGDADOS_ICON_BASE64}";
        function applyBranding() {{
          const doc = window.parent.document;
          if (doc.title !== title) doc.title = title;
          const icons = doc.querySelectorAll("link[rel~='icon'], link[rel='shortcut icon'], link[rel='apple-touch-icon']");
          icons.forEach(function(el) {{ el.remove(); }});
          const icon = doc.createElement('link');
          icon.rel = 'icon';
          icon.type = 'image/png';
          icon.href = href;
          doc.head.appendChild(icon);
        }}
        applyBranding();
        setInterval(applyBranding, 1000);
        </script>
        """,
        height=0,
    )


def render_auth_gate_safe_logo() -> bool:
    force_bigdados_branding()
    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        f"""
        <style>
          [data-testid="stSidebar"] {{ filter: blur(1.8px); opacity: 0.56; }}
          .bigdados-auth-shell {{
            max-width: 560px;
            margin: 3.2vh auto 0 auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
            align-items: stretch;
          }}
          .bigdados-login-logo {{
            width: 88px;
            height: 88px;
            object-fit: contain;
            margin: 0 auto 0 auto;
            border-radius: 18px;
          }}
          .bigdados-auth-card {{
            padding: 22px 26px;
            border-radius: 22px;
            border: 1px solid color-mix(in srgb, var(--text-color) 18%, transparent);
            background: color-mix(in srgb, var(--secondary-background-color) 92%, transparent);
            color: var(--text-color);
            box-shadow: 0 18px 60px rgba(0, 0, 0, 0.18);
          }}
          .bigdados-auth-title {{
            font-size: 27px;
            line-height: 1.12;
            font-weight: 850;
            letter-spacing: -0.03em;
            margin-bottom: 8px;
            color: var(--text-color);
          }}
          .bigdados-auth-subtitle {{
            color: color-mix(in srgb, var(--text-color) 72%, transparent);
            font-size: 14px;
            line-height: 1.42;
          }}
          .bigdados-auth-input-wrap {{
            max-width: 560px;
            margin: 10px auto 0 auto;
            padding: 14px 16px 12px 16px;
            border-radius: 16px;
            border: 1px solid color-mix(in srgb, var(--text-color) 18%, transparent);
            background: color-mix(in srgb, var(--secondary-background-color) 88%, transparent);
            color: var(--text-color);
            box-shadow: 0 14px 42px rgba(0, 0, 0, 0.14);
          }}
          .stAlert {{ max-width: 560px; margin-left: auto; margin-right: auto; }}
        </style>
        <div class="bigdados-auth-shell">
          <img class="bigdados-login-logo" src="data:image/png;base64,{BIGDADOS_ICON_BASE64}" />
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

    with st.container():
        st.markdown('<div class="bigdados-auth-input-wrap">', unsafe_allow_html=True)
        pat = st.text_input(
            "Personal Access Token do Dremio",
            value="",
            type="password",
            placeholder="Cole aqui o seu PAT do Dremio",
            key="safe_dremio_pat_unlock",
        )
        submitted = st.button("Desbloquear app", type="primary", use_container_width=True, key="safe_unlock_button")
        st.markdown('</div>', unsafe_allow_html=True)

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


def render_sidebar_with_branding():
    force_bigdados_branding()
    return phase12.phase11.phase6.render_sidebar_without_session_block()


def render_chat_with_branding_and_results():
    force_bigdados_branding()
    return phase10.render_chat_persistent_results()


entry.base_app.render_auth_gate = render_auth_gate_safe_logo
entry.base_app.render_sidebar = render_sidebar_with_branding
entry.base_app.render_chat = render_chat_with_branding_and_results
entry.base_app.render_download_buttons = phase10.render_live_result_block
entry.base_app.append_persistent_message = phase12.phase11.append_persistent_message_with_latest_result
entry.base_app.load_conversation = phase12.phase11.load_conversation_with_result_fallback

if __name__ == "__main__":
    entry.base_app.main()
