import os
import sys
import subprocess
from pathlib import Path

from spreadsheet_engine import SpreadsheetEngine
from dremio_engine import DremioEngine
from agent import Agent


def check_gcp_auth() -> bool:
    try:
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def setup_spreadsheet() -> SpreadsheetEngine:
    print("\n=== MODO PLANILHA ===\n")
    print("Aceita arquivos locais OU caminhos GCS (gs://bucket/path/file.parquet)\n")

    engine = SpreadsheetEngine()

    hmac_id = os.getenv("GCS_HMAC_KEY_ID")
    hmac_secret = os.getenv("GCS_HMAC_SECRET")
    if hmac_id and hmac_secret:
        engine.configure_gcs(hmac_id, hmac_secret)
        print("  ✓ GCS configurado via HMAC keys do ambiente\n")

    while True:
        path = input("Caminho do arquivo (local ou gs://) ou ENTER para terminar: ").strip()
        if not path:
            break

        suggested = Path(path.split("/")[-1]).stem.lower().replace("-", "_").replace(" ", "_")
        custom = input(f"  Nome da tabela [{suggested}]: ").strip() or suggested

        try:
            table = engine.load_file(path, custom)
            info = engine.describe_table(table)
            print(f"  ✓ '{table}': {info.row_count:,} linhas, {len(info.columns)} colunas")
        except Exception as e:
            print(f"  ❌ Erro: {e}")

    if not engine.list_tables():
        print("Nenhuma tabela carregada. Saindo.")
        sys.exit(1)
    return engine


def setup_dremio() -> DremioEngine:
    print("\n=== MODO DREMIO ===\n")

    host = os.getenv("DREMIO_HOST") or input("Host do Dremio: ").strip()
    pat = os.getenv("DREMIO_PAT") or input("Personal Access Token: ").strip()

    is_cloud = input("É Dremio Cloud? [s/N]: ").strip().lower() == "s"
    project_id = None
    if is_cloud:
        project_id = os.getenv("DREMIO_PROJECT_ID") or input("Project ID Dremio Cloud: ").strip()

    paths = input("Workspaces para listar (vírgula, ENTER p/ todos): ").strip()
    allowed = [p.strip() for p in paths.split(",")] if paths else None

    engine = DremioEngine(
        host=host, pat=pat, project_id=project_id,
        is_cloud=is_cloud, allowed_paths=allowed,
    )

    print("\nValidando conexão...")
    try:
        tables = engine.list_tables()
        print(f"  ✓ Conectado. {len(tables)} tabelas visíveis.")
    except Exception as e:
        print(f"  ❌ Falha: {e}")
        sys.exit(1)
    return engine


def chat_loop(agent: Agent):
    print(f"\n{'='*60}")
    print(f"Agente pronto. Engine: {agent.engine.engine_name}")
    print(f"Modelo: {agent.model} (via Vertex AI)")
    print(f"{'='*60}")
    print("Digite suas perguntas. Ctrl+C ou 'sair' para encerrar.\n")

    while True:
        try:
            user_input = input("\n💬 Você: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAté mais!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("sair", "exit", "quit"):
            print("Até mais!")
            break

        print("\n🤔 Pensando...\n")
        try:
            response = agent.chat(user_input)
            print(f"\n🤖 Agente:\n{response}\n")
        except Exception as e:
            print(f"\n❌ Erro: {e}\n")


def main():
    if not check_gcp_auth():
        print("❌ Application Default Credentials não configurado.")
        print("   Rode: gcloud auth application-default login")
        sys.exit(1)

    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        print("❌ Defina GOOGLE_CLOUD_PROJECT no ambiente.")
        print('   Ex: export GOOGLE_CLOUD_PROJECT="meu-projeto-123"')
        sys.exit(1)

    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║   Cartola Data Workspace — Spike Vertex AI / Gemini       ║
║                                                           ║
║   Projeto GCP: {project:<41}║
║   Location:    {location:<41}║
╚═══════════════════════════════════════════════════════════╝
    """)

    print("Escolha a fonte de dados:")
    print("  1) Planilha (local ou GCS via DuckDB)")
    print("  2) Dremio (via PAT)")

    choice = input("\nOpção [1/2]: ").strip()

    if choice == "1":
        engine = setup_spreadsheet()
    elif choice == "2":
        engine = setup_dremio()
    else:
        print("Opção inválida.")
        sys.exit(1)

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    agent = Agent(engine, model=model, project_id=project, location=location)
    chat_loop(agent)


if __name__ == "__main__":
    main()
