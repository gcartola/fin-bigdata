import streamlit as st

st.set_page_config(page_title="BigDados", page_icon="🎲", layout="wide")
st.set_page_config = lambda *args, **kwargs: None

import pandas as pd
import streamlit.components.v1 as components

import app_phase12 as phase12

entry = phase12.entry
phase10 = phase12.phase10
phase11 = phase12.phase11

# Versão reduzida da imagem enviada para uso em favicon e tela inicial.
# Mantém o app leve e evita scroll na tela de desbloqueio.
BIGDADOS_LOGO_BASE64 = "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" 


def force_bigdados_branding():
    components.html(
        f"""
        <script>
        const title = "BigDados";
        const href = "data:image/png;base64,{BIGDADOS_LOGO_BASE64}";
        function applyBranding() {{
          const doc = window.parent.document;
          if (doc.title !== title) doc.title = title;
          doc.querySelectorAll("link[rel~='icon'], link[rel='shortcut icon'], link[rel='apple-touch-icon']").forEach(el => el.remove());
          const icon = doc.createElement('link');
          icon.rel = 'icon';
          icon.type = 'image/png';
          icon.href = href;
          doc.head.appendChild(icon);
        }}
        applyBranding();
        new MutationObserver(applyBranding).observe(window.parent.document.head, {{ childList: true, subtree: true }});
        setInterval(applyBranding, 750);
        </script>
        """,
        height=0,
    )


def render_auth_gate_with_logo() -> bool:
    force_bigdados_branding()
    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        f"""
        <style>
          [data-testid="stSidebar"] {{ filter: blur(1.8px); opacity: 0.56; }}
          .bigdados-auth-shell {{
            max-width: 560px;
            margin: 3.5vh auto 0 auto;
            display: flex;
            flex-direction: column;
            gap: 14px;
            align-items: stretch;
          }}
          .bigdados-login-logo {{
            display: block;
            width: 108px;
            height: 108px;
            object-fit: contain;
            margin: 0 auto 2px auto;
            border-radius: 22px;
          }}
          .bigdados-auth-card {{
            padding: 24px 28px;
            border-radius: 22px;
            border: 1px solid color-mix(in srgb, var(--text-color) 18%, transparent);
            background: color-mix(in srgb, var(--secondary-background-color) 92%, transparent);
            color: var(--text-color);
            box-shadow: 0 22px 70px rgba(0, 0, 0, 0.20);
          }}
          .bigdados-auth-title {{
            font-size: 28px;
            line-height: 1.16;
            font-weight: 850;
            letter-spacing: -0.03em;
            margin-bottom: 10px;
            color: var(--text-color);
          }}
          .bigdados-auth-subtitle {{
            color: color-mix(in srgb, var(--text-color) 72%, transparent);
            font-size: 14px;
            line-height: 1.45;
          }}
          div[data-testid="stForm"] {{
            max-width: 560px;
            margin: 14px auto 0 auto;
            padding: 14px 16px 12px 16px;
            border-radius: 16px;
            border: 1px solid color-mix(in srgb, var(--text-color) 18%, transparent);
            background: color-mix(in srgb, var(--secondary-background-color) 88%, transparent);
            color: var(--text-color);
            box-shadow: 0 16px 45px rgba(0, 0, 0, 0.16);
          }}
          div[data-testid="stForm"] label,
          div[data-testid="stForm"] p,
          div[data-testid="stForm"] span {{
            color: color-mix(in srgb, var(--text-color) 78%, transparent) !important;
          }}
          div[data-testid="stForm"] button[kind="primary"] {{ border-radius: 10px; margin-top: 6px; }}
          div[data-testid="stForm"] input {{ border-radius: 10px; }}
          .stAlert {{ max-width: 560px; margin-left: auto; margin-right: auto; }}
        </style>
        <div class="bigdados-auth-shell">
          <img class="bigdados-login-logo" src="data:image/png;base64,{BIGDADOS_LOGO_BASE64}" />
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
        pat = st.text_input("Personal Access Token do Dremio", value="", type="password", placeholder="Cole aqui o seu PAT do Dremio")
        submitted = st.form_submit_button("Desbloquear app", type="primary", use_container_width=True)

    if submitted:
        try:
            authenticator = entry.DremioPATAuthenticator(entry.base_app.DREMIO_CLOUD_HOST, entry.base_app.DREMIO_CLOUD_PROJECT_ID, is_cloud=True)
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


def scalar_for_firestore(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return str(value)


def query_result_payload(result, max_rows: int = 80) -> dict | None:
    if not result or not getattr(result, "rows", None):
        return None
    columns = list(result.columns)
    rows = []
    for row in result.rows[:max_rows]:
        rows.append({col: scalar_for_firestore(value) for col, value in zip(columns, row)})
    return {
        "columns": columns,
        "rows": rows,
        "sample_row_count": len(rows),
        "row_count": int(result.row_count or len(rows)),
        "sql_executed": getattr(result, "sql_executed", None),
        "execution_time_ms": getattr(result, "execution_time_ms", None),
    }


def dataframe_from_payload(payload: dict) -> pd.DataFrame:
    return pd.DataFrame(payload.get("rows") or [], columns=payload.get("columns") or [])


def render_payload_result_block(payload: dict, key: str = "persisted"):
    if not payload or not payload.get("rows"):
        return
    df = dataframe_from_payload(payload)
    total_rows = payload.get("row_count") or len(df)
    sample_rows = payload.get("sample_row_count") or len(df)
    sql = payload.get("sql_executed") or ""
    st.markdown("### Resultado da consulta")
    with st.container(border=True):
        caption = f"{total_rows:,} linha(s) retornada(s) · {len(df.columns)} coluna(s)"
        if sample_rows < total_rows:
            caption += f" · exibindo amostra persistida de {sample_rows:,} linha(s)"
        if payload.get("execution_time_ms"):
            caption += f" · {payload.get('execution_time_ms')}ms"
        st.caption(caption)
        st.dataframe(df, use_container_width=True, hide_index=True)
        with st.expander("SQL gerado", expanded=False):
            if sql:
                phase10.render_copy_sql_button(sql, key)
                st.code(sql, language="sql")
            else:
                st.caption("Nenhum SQL registrado para este resultado.")


phase10.query_result_payload = query_result_payload
phase10.dataframe_from_payload = dataframe_from_payload
phase10.render_payload_result_block = render_payload_result_block
phase12.force_bigdados_branding = force_bigdados_branding


def render_sidebar_with_branding():
    force_bigdados_branding()
    return phase12.phase11.phase6.render_sidebar_without_session_block()


def render_chat_with_branding_and_results():
    force_bigdados_branding()
    return phase10.render_chat_persistent_results()


entry.base_app.append_persistent_message = phase12.phase11.append_persistent_message_with_latest_result
entry.base_app.load_conversation = phase12.phase11.load_conversation_with_result_fallback
entry.base_app.render_sidebar = render_sidebar_with_branding
entry.base_app.render_auth_gate = render_auth_gate_with_logo
entry.base_app.render_chat = render_chat_with_branding_and_results
entry.base_app.render_download_buttons = phase10.render_live_result_block

if __name__ == "__main__":
    entry.base_app.main()
