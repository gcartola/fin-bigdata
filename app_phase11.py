import streamlit as st

st.set_page_config(page_title="BigDados", page_icon="📊", layout="wide")
st.set_page_config = lambda *args, **kwargs: None

import streamlit.components.v1 as components

import app_phase10 as phase10

entry = phase10.entry
phase8 = phase10.phase8
phase6 = phase10.phase6

BIGDADOS_FAVICON_SVG = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
<rect width='64' height='64' rx='12' fill='#ffffff'/>
<rect x='8' y='8' width='48' height='48' rx='2' fill='#ffffff' stroke='#0f172a' stroke-width='4'/>
<rect x='16' y='34' width='7' height='14' fill='#22c55e'/>
<rect x='28' y='20' width='7' height='28' fill='#ef4444'/>
<rect x='40' y='12' width='7' height='36' fill='#3b82f6'/>
</svg>"""


def force_bigdados_branding():
    # Streamlit às vezes recoloca o título/favicon default em reruns/reconexões.
    # Este observer mantém a aba estável sem depender de um único disparo de JS.
    components.html(
        f"""
        <script>
        const title = "BigDados";
        const svg = {BIGDADOS_FAVICON_SVG!r};
        const href = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);

        function applyBranding() {{
          if (window.parent.document.title !== title) {{
            window.parent.document.title = title;
          }}
          const doc = window.parent.document;
          let icon = doc.querySelector("link[rel='icon']") || doc.querySelector("link[rel='shortcut icon']");
          if (!icon) {{
            icon = doc.createElement('link');
            icon.rel = 'icon';
            doc.head.appendChild(icon);
          }}
          if (icon.href !== href) {{
            icon.type = 'image/svg+xml';
            icon.href = href;
          }}
        }}

        applyBranding();
        const observer = new MutationObserver(applyBranding);
        observer.observe(window.parent.document.head, {{ childList: true, subtree: true, characterData: true }});
        setInterval(applyBranding, 1000);
        </script>
        """,
        height=0,
    )


def append_persistent_message_with_latest_result(role: str, content: str, **metadata):
    conversation_id = entry.base_app.ensure_conversation(
        title=entry.base_app.build_conversation_title(content) if role == "user" else None
    )
    store = entry.base_app.memory()
    if store and conversation_id and not str(conversation_id).startswith("local-"):
        store.append_message(conversation_id, role, content, **metadata)
        query_result = metadata.get("query_result")
        if query_result:
            store.update_conversation(
                conversation_id,
                latest_query_result=query_result,
                last_query_sql=query_result.get("sql_executed"),
                last_result_summary=metadata.get("query_result_summary"),
            )
    else:
        entry.base_app.upsert_local_conversation(conversation_id, entry.base_app.build_conversation_title(content) if role == "user" else None)
    entry.base_app.refresh_conversations()


def load_conversation_with_result_fallback(conversation_id: str):
    store = entry.base_app.memory()
    messages = []
    conversation = None
    if store and not str(conversation_id).startswith("local-"):
        messages = store.get_messages(conversation_id, limit=50)
        conversation = store.get_conversation(conversation_id)

    hydrated = []
    for m in messages:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        item = {"role": role, "content": m.get("content", "")}
        query_result = m.get("query_result")
        if query_result:
            item["query_result"] = query_result
        hydrated.append(item)

    # Fallback para conversas em que o resultado foi salvo no documento da conversa,
    # mas não veio anexado à mensagem por algum motivo.
    latest_result = (conversation or {}).get("latest_query_result")
    if latest_result and hydrated:
        for item in reversed(hydrated):
            if item.get("role") == "assistant":
                item.setdefault("query_result", latest_result)
                break

    st.session_state.conversation_id = conversation_id
    st.session_state.messages = hydrated
    if st.session_state.get("agent"):
        st.session_state.agent.load_history(st.session_state.messages)

    try:
        entry.hydrate_workspace_from_conversation(conversation_id)
    except Exception:
        pass


def render_sidebar_with_branding():
    force_bigdados_branding()
    return phase6.render_sidebar_without_session_block()


def render_auth_gate_with_branding() -> bool:
    force_bigdados_branding()
    return phase6.render_auth_gate_with_title()


def render_chat_with_branding_and_results():
    force_bigdados_branding()
    return phase10.render_chat_persistent_results()


entry.base_app.append_persistent_message = append_persistent_message_with_latest_result
entry.base_app.load_conversation = load_conversation_with_result_fallback
entry.base_app.render_sidebar = render_sidebar_with_branding
entry.base_app.render_auth_gate = render_auth_gate_with_branding
entry.base_app.render_chat = render_chat_with_branding_and_results
entry.base_app.render_download_buttons = phase10.render_live_result_block

if __name__ == "__main__":
    entry.base_app.main()
