import streamlit as st

st.set_page_config(page_title="BigDados", page_icon="🎲", layout="wide")
st.set_page_config = lambda *args, **kwargs: None

import pandas as pd
import streamlit.components.v1 as components

import app_phase11 as phase11

entry = phase11.entry
phase10 = phase11.phase10

BIGDADOS_FAVICON_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAADO0lEQVR42lWTXWhbdRjGf///OUmapE1Slulmu81260YdtmtBmBcTBdlAhroJgyG6euUXKExlNyIMvFEQRVAYXlSEMtj8aBGhFWGFOku71q4TV7G0W7+S9jTJSdbm5OQkOa8XmaDPzXvzPs/7XvwelU6nBUAp8H0BIBJpwM7fI5vLo7XBzh0JYrFGisUSSisUIFL3mNyX7wuhYJCaX2Pu70WKpTILd1YQgZ3JZpKJGJ2H2tFa43keSmlEQCul6lfDDaQ2LG7dnmdpZQPHKTO/sMzd5RQnTzyFDgSZnp1j3coQDof592uVTqclYJpM3fyTXGELBMpehatDI1zt/5RIpL7semW+GxxBm5pkc5zerk4qlSrk7ZyMXZ+Qa9cnxc4X5PhzfTJ+46b8V8O/jEn/wPdy/Nk+yeZtGfp5VMZ+m5C8nRNTKUU2X6Cr+1ES8Rgjg/0AVGs1xidn2Np2+OKrAV595QwjQ/0srm2AGcTK2BiGxqxWqyTiMb65PIhWirdfP0e1WiEejfLj8CiG1vx05RIpK8v4zF98PfAtPsILzzyJL4KpDQPPq3CgbS+T07OUXY9SuUwgGODji+/iAzNzCyyvWkQiIZxikY6D+6lVa4gvaENrio5DT/dh3n/vTcyASXrdou+1CyylLX6d+oPzFz6kcK9AIGDS99IZOjr2U3JdtNZo3/dBKbacIkor3jj/AStraVp27yKbtclkbXbtfgBrM8NHn3yJj6LouNSRE5Sdy8iN2TmGRyeIhEMkEjEaIxHOnT3F6to680trNDY1MTxyjaJTxtneYqvk8uLpExx7rAtTgESskVAwiO/Dy2dPYxcKpDcz+EC1KliWTU/PEaLRKJev/EBjUxMP7ojji6Bd16N9XyuP9z5CW9se7iylSK1ZvPXORRzXpeRV+OzzS6TWLVbWN+ns7OD5p4/Svq8F1y1jKqXwvApPHO1lcWmV8anfCYajtLa2UHJcXLdMczJJLl8gWStx8tgR9rY+hFNyUUrVUa6XyachFEIpmL51m5UNG08M8oVtGkzoPriH7sOH8EVwXQ/D0P8PABDxEYGmxgiZrM3c/F0MQ9N54GESiTjbRaduUtyfmn8AjJOeOzOryQ4AAAAASUVORK5CYII="


def force_bigdados_branding():
    components.html(
        f"""
        <script>
        const title = "BigDados";
        const href = "data:image/png;base64,{BIGDADOS_FAVICON_PNG_BASE64}";
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
        new MutationObserver(applyBranding).observe(window.parent.document.head, {childList: true, subtree: true});
        setInterval(applyBranding, 750);
        </script>
        """,
        height=0,
    )


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
phase11.force_bigdados_branding = force_bigdados_branding


def render_sidebar_with_branding():
    force_bigdados_branding()
    return phase11.phase6.render_sidebar_without_session_block()


def render_auth_gate_with_branding() -> bool:
    force_bigdados_branding()
    return phase11.phase6.render_auth_gate_with_title()


def render_chat_with_branding_and_results():
    force_bigdados_branding()
    return phase10.render_chat_persistent_results()


entry.base_app.append_persistent_message = phase11.append_persistent_message_with_latest_result
entry.base_app.load_conversation = phase11.load_conversation_with_result_fallback
entry.base_app.render_sidebar = render_sidebar_with_branding
entry.base_app.render_auth_gate = render_auth_gate_with_branding
entry.base_app.render_chat = render_chat_with_branding_and_results
entry.base_app.render_download_buttons = phase10.render_live_result_block

if __name__ == "__main__":
    entry.base_app.main()
