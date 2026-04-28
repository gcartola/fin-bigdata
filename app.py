import os
import tempfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from agent import Agent
from dremio_engine import DremioEngine
from spreadsheet_engine import SpreadsheetEngine


st.set_page_config(page_title="Fin BigData", page_icon="📊", layout="wide")


def init_state():
    if "engine" not in st.session_state:
        st.session_state.engine = None
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "loaded_files" not in st.session_state:
        st.session_state.loaded_files = []


def get_vertex_config():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1").strip()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    return project_id, location, model


def create_agent(engine):
    project_id, location, model = get_vertex_config()
    if not project_id:
        st.error("Defina GOOGLE_CLOUD_PROJECT no ambiente antes de iniciar o agente.")
        return None
    return Agent(engine, model=model, project_id=project_id, location=location)


def save_uploaded_file(uploaded_file) -> str:
    tmp_dir = Path(tempfile.gettempdir()) / "fin-bigdata-upload"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    target = tmp_dir / uploaded_file.name
    target.write_bytes(uploaded_file.getbuffer())
    return str(target)


def render_download_buttons():
    agent = st.session_state.get("agent")
    if not agent:
        return

    result = getattr(agent, "last_query_result", None)
    if not result or not result.rows:
        return

    df = pd.DataFrame(result.rows, columns=result.columns)
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")

    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="resultado")

    st.divider()
    st.caption(f"Resultado disponível para download: {len(df):,} linhas")
    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            label="Baixar CSV",
            data=csv_bytes,
            file_name="resultado_fin_bigdata.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col2:
        st.download_button(
            label="Baixar Excel",
            data=excel_buffer.getvalue(),
            file_name="resultado_fin_bigdata.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def setup_spreadsheet_ui():
    st.subheader("Modo Planilha")
    st.caption("Carregue CSV, XLSX ou Parquet. O spike usa DuckDB para consultar os dados.")

    uploads = st.file_uploader("Arquivos", type=["csv", "xlsx", "xls", "parquet"], accept_multiple_files=True)

    if st.button("Carregar arquivos", type="primary", disabled=not uploads):
        engine = SpreadsheetEngine()

        hmac_id = os.getenv("GCS_HMAC_KEY_ID")
        hmac_secret = os.getenv("GCS_HMAC_SECRET")
        if hmac_id and hmac_secret:
            engine.configure_gcs(hmac_id, hmac_secret)

        loaded = []
        for uploaded in uploads:
            path = save_uploaded_file(uploaded)
            table_name = Path(uploaded.name).stem.lower().replace("-", "_").replace(" ", "_")
            try:
                table = engine.load_file(path, table_name)
                info = engine.describe_table(table)
                loaded.append(f"{info.full_path} — {info.row_count:,} linhas")
            except Exception as exc:
                st.error(f"Erro ao carregar {uploaded.name}: {exc}")
                return

        agent = create_agent(engine)
        if agent:
            st.session_state.engine = engine
            st.session_state.agent = agent
            st.session_state.loaded_files = loaded
            st.session_state.messages = []
            st.success("Arquivos carregados e agente inicializado.")


def setup_dremio_ui():
    st.subheader("Modo Dremio")
    st.caption("Use o PAT do próprio usuário. O agente continua sendo Gemini via Vertex AI.")

    default_host = os.getenv("DREMIO_HOST", "")
    host = st.text_input("Host do Dremio", value=default_host, placeholder="https://dremio.empresa.com")
    pat = st.text_input("Personal Access Token", value=os.getenv("DREMIO_PAT", ""), type="password")
    is_cloud = st.checkbox("É Dremio Cloud?", value=False)
    project_id = st.text_input("Project ID Dremio Cloud", value=os.getenv("DREMIO_PROJECT_ID", "")) if is_cloud else None
    paths_raw = st.text_input("Workspaces para listar", placeholder="Comercial,Financeiro")

    if st.button("Conectar Dremio", type="primary", disabled=not host or not pat):
        allowed = [p.strip() for p in paths_raw.split(",") if p.strip()] if paths_raw else None
        try:
            engine = DremioEngine(host=host, pat=pat, project_id=project_id, is_cloud=is_cloud, allowed_paths=allowed)
            tables = engine.list_tables()
            agent = create_agent(engine)
            if agent:
                st.session_state.engine = engine
                st.session_state.agent = agent
                st.session_state.loaded_files = [f"{len(tables)} tabelas visíveis no Dremio"]
                st.session_state.messages = []
                st.success("Dremio conectado e agente inicializado.")
        except Exception as exc:
            st.error(f"Falha ao conectar no Dremio: {exc}")


def render_sidebar():
    project_id, location, model = get_vertex_config()

    with st.sidebar:
        st.title("Fin BigData")
        st.caption("Spike GCP + Gemini + DuckDB/Dremio")

        st.markdown("### Vertex AI")
        st.write(f"Projeto: `{project_id or 'não definido'}`")
        st.write(f"Região: `{location}`")
        st.write(f"Modelo: `{model}`")

        st.markdown("### Fonte de dados")
        mode = st.radio("Modo", ["Planilha", "Dremio"], horizontal=True)

        st.divider()
        if mode == "Planilha":
            setup_spreadsheet_ui()
        else:
            setup_dremio_ui()

        st.divider()
        st.markdown("### Estado")
        if st.session_state.engine:
            st.success(st.session_state.engine.engine_name)
            for item in st.session_state.loaded_files:
                st.caption(item)
        else:
            st.warning("Nenhuma engine ativa.")

        if st.button("Resetar sessão"):
            st.session_state.engine = None
            st.session_state.agent = None
            st.session_state.messages = []
            st.session_state.loaded_files = []
            st.rerun()


def render_chat():
    st.title("📊 Fin BigData")
    st.caption("Bancada analítica assistida por Gemini. O agente consulta dados estruturados, não arquivo bruto no prompt.")

    if not st.session_state.agent:
        st.info("Escolha uma fonte de dados na barra lateral para iniciar o agente.")
        return

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    render_download_buttons()

    user_input = st.chat_input("Pergunte algo sobre os dados...")
    if not user_input:
        return

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Consultando dados e pensando..."):
            try:
                response = st.session_state.agent.chat(user_input)
            except Exception as exc:
                response = f"Erro ao processar pergunta: {exc}"
            st.markdown(response)
            render_download_buttons()

    st.session_state.messages.append({"role": "assistant", "content": response})


def main():
    init_state()
    render_sidebar()
    render_chat()


if __name__ == "__main__":
    main()
