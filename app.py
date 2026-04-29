import os
import tempfile
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from agent import Agent
from dremio_engine import DremioEngine
from gcs_upload import create_signed_upload_url, get_gcs_hmac_credentials, get_upload_bucket
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
    if "signed_upload" not in st.session_state:
        st.session_state.signed_upload = None


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


def configure_engine_gcs(engine: SpreadsheetEngine):
    hmac_id, hmac_secret = get_gcs_hmac_credentials()
    if hmac_id and hmac_secret:
        engine.configure_gcs(hmac_id, hmac_secret)
    else:
        engine.configure_gcs()


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


def start_spreadsheet_agent(engine: SpreadsheetEngine, loaded: list[str]):
    agent = create_agent(engine)
    if agent:
        st.session_state.engine = engine
        st.session_state.agent = agent
        st.session_state.loaded_files = loaded
        st.session_state.messages = []
        st.success("Arquivos carregados e agente inicializado.")


def setup_local_spreadsheet_upload():
    st.markdown("#### Upload local")
    st.caption("Indicado para arquivos pequenos. Em Cloud Run, prefira o upload via GCS para evitar limite de request.")

    uploads = st.file_uploader("Arquivos", type=["csv", "xlsx", "xls", "parquet"], accept_multiple_files=True)

    if st.button("Carregar arquivos locais", type="primary", disabled=not uploads):
        engine = SpreadsheetEngine()
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

        start_spreadsheet_agent(engine, loaded)


def render_signed_upload_component(signed_url: str, gcs_uri: str):
    components.html(
        f"""
        <div style="font-family: sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 12px;">
          <p><strong>Upload direto para GCS</strong></p>
          <input id="file" type="file" />
          <button id="upload" style="margin-left: 8px;">Enviar para GCS</button>
          <pre id="status" style="white-space: pre-wrap;"></pre>
        </div>
        <script>
        const signedUrl = {signed_url!r};
        const gcsUri = {gcs_uri!r};
        document.getElementById('upload').onclick = async () => {{
          const file = document.getElementById('file').files[0];
          const status = document.getElementById('status');
          if (!file) {{
            status.textContent = 'Selecione um arquivo primeiro.';
            return;
          }}
          status.textContent = 'Enviando... não feche esta página.';
          try {{
            const response = await fetch(signedUrl, {{
              method: 'PUT',
              body: file
            }});
            const detail = await response.text();
            if (!response.ok) {{
              throw new Error(`HTTP ${{response.status}} ${{response.statusText}} ${{detail}}`);
            }}
            status.textContent = `Upload concluído. Agora clique em "Usar arquivo enviado" no app.\n${{gcsUri}}`;
          }} catch (err) {{
            status.textContent = `Falha no upload: ${{err.message}}`;
          }}
        }};
        </script>
        """,
        height=220,
    )


def setup_gcs_spreadsheet_upload():
    st.markdown("#### Upload grande via GCS")
    st.caption("O arquivo vai direto do navegador para o bucket. O Streamlit recebe só o caminho gs:// para consulta.")

    try:
        bucket = get_upload_bucket()
        st.caption(f"Bucket configurado: `{bucket}`")
    except Exception as exc:
        st.warning(f"Upload via GCS indisponível: {exc}")
        return

    filename = st.text_input("Nome do arquivo", placeholder="base_cobranca.xlsx, base_cobranca.csv ou base_cobranca.parquet")

    if st.button("Gerar signed URL", disabled=not filename):
        try:
            st.session_state.signed_upload = create_signed_upload_url(filename=filename)
        except Exception as exc:
            st.error(f"Falha ao gerar signed URL: {exc}")

    signed_upload = st.session_state.get("signed_upload")
    if signed_upload:
        st.code(signed_upload.gcs_uri)
        render_signed_upload_component(signed_upload.signed_url, signed_upload.gcs_uri)

        table_name = Path(signed_upload.object_name).stem.lower().replace("-", "_").replace(" ", "_")
        table_name = st.text_input("Nome da tabela no DuckDB", value=table_name)
        if st.button("Usar arquivo enviado", type="primary"):
            engine = SpreadsheetEngine()
            try:
                configure_engine_gcs(engine)
                table = engine.load_file(signed_upload.gcs_uri, table_name)
                info = engine.describe_table(table)
                start_spreadsheet_agent(engine, [f"{info.full_path} — {info.row_count:,} linhas — {signed_upload.gcs_uri}"])
            except Exception as exc:
                st.error(f"Erro ao carregar arquivo do GCS: {exc}")


def setup_spreadsheet_ui():
    st.subheader("Modo Planilha")
    st.caption("Use DuckDB para consultar CSV, XLSX ou Parquet. Para arquivos grandes, use GCS.")

    tab_gcs, tab_local = st.tabs(["GCS / arquivo grande", "Upload local / dev"])
    with tab_gcs:
        setup_gcs_spreadsheet_upload()
    with tab_local:
        setup_local_spreadsheet_upload()


def setup_dremio_ui():
    st.subheader("Modo Dremio")
    st.caption("Use PAT individual ou um PAT de serviço vindo do Secret Manager.")

    default_host = os.getenv("DREMIO_HOST", "")
    host = st.text_input("Host do Dremio", value=default_host, placeholder="https://dremio.empresa.com")
    server_pat = os.getenv("DREMIO_PAT", "").strip()
    use_server_pat = False
    if server_pat:
        use_server_pat = st.checkbox("Usar PAT de serviço configurado no servidor", value=False)

    pat = ""
    if not use_server_pat:
        pat = st.text_input(
            "Personal Access Token",
            value="",
            type="password",
            placeholder="Cole aqui o seu PAT do Dremio",
        )
    effective_pat = server_pat if use_server_pat else pat

    is_cloud = st.checkbox("É Dremio Cloud?", value=False)
    project_id = st.text_input("Project ID Dremio Cloud", value=os.getenv("DREMIO_PROJECT_ID", "")) if is_cloud else None
    paths_raw = st.text_input("Workspaces para listar", placeholder="Comercial,Financeiro")

    if st.button("Conectar Dremio", type="primary", disabled=not host or not effective_pat):
        allowed = [p.strip() for p in paths_raw.split(",") if p.strip()] if paths_raw else None
        try:
            engine = DremioEngine(host=host, pat=effective_pat, project_id=project_id, is_cloud=is_cloud, allowed_paths=allowed)
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
        st.caption("Produto analítico: Cloud Run + Vertex AI + DuckDB/Dremio")

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
            st.session_state.signed_upload = None
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
