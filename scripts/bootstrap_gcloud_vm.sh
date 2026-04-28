#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/fin-bigdata}"
REPO_URL="${REPO_URL:-https://github.com/gcartola/fin-bigdata.git}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

printf '\n== Fin BigData bootstrap ==\n'
printf 'Projeto local: %s\n' "$PROJECT_DIR"
printf 'Repo: %s\n\n' "$REPO_URL"

if ! command -v git >/dev/null 2>&1; then
  echo 'Instalando git...'
  sudo apt-get update
  sudo apt-get install -y git
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo 'Instalando Python...'
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip
fi

if ! dpkg -s python3-venv >/dev/null 2>&1; then
  echo 'Instalando python3-venv...'
  sudo apt-get update
  sudo apt-get install -y python3-venv
fi

if [ ! -d "$PROJECT_DIR/.git" ]; then
  echo 'Clonando repositório...'
  git clone "$REPO_URL" "$PROJECT_DIR"
else
  echo 'Repositório já existe. Atualizando main...'
  cd "$PROJECT_DIR"
  git fetch origin
  git checkout main
  git pull origin main
fi

cd "$PROJECT_DIR"

mkdir -p data exports logs tmp

if [ ! -d ".venv" ]; then
  echo 'Criando ambiente virtual Python...'
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel

if [ -f requirements.txt ]; then
  echo 'Instalando dependências Python...'
  pip install -r requirements.txt
else
  echo 'requirements.txt não encontrado. Instalando dependências mínimas...'
  pip install google-genai google-auth duckdb requests polars
fi

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
  echo 'Criando .env a partir do .env.example...'
  cp .env.example .env
fi

cat <<'EOF'

Bootstrap concluído.

Próximos passos:

1) Edite o arquivo .env com seus valores reais:
   nano .env

2) Garanta autenticação GCP na VM:
   gcloud auth application-default login

   Em VM/Cloud Run com service account correta, esse passo pode não ser necessário.

3) Exporte as variáveis do .env no shell atual:
   set -a
   source .env
   set +a

4) Rode o spike:
   source .venv/bin/activate
   python main.py

EOF
