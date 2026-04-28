#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-${PROJECT_ID:-}}"
PROJECT_NAME="${PROJECT_NAME:-Fin BigData}"
BILLING_ACCOUNT_ID="${BILLING_ACCOUNT_ID:-}"
ORG_ID="${ORG_ID:-}"
FOLDER_ID="${FOLDER_ID:-}"
REGION="${REGION:-us-central1}"

if [ -z "$PROJECT_ID" ]; then
  echo "Erro: informe o PROJECT_ID."
  echo "Exemplo: export PROJECT_ID=fin-bigdata-123"
  exit 1
fi

printf '\n== Criação/Bootstrap de Projeto GCP ==\n'
printf 'Project ID:   %s\n' "$PROJECT_ID"
printf 'Project name: %s\n' "$PROJECT_NAME"
printf 'Region:       %s\n\n' "$REGION"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "Erro: gcloud CLI não encontrado. Rode este script no Cloud Shell ou instale o Google Cloud SDK."
  exit 1
fi

if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  echo "Projeto já existe: $PROJECT_ID"
else
  echo "Criando projeto..."
  CREATE_ARGS=("$PROJECT_ID" "--name=$PROJECT_NAME")

  if [ -n "$FOLDER_ID" ]; then
    CREATE_ARGS+=("--folder=$FOLDER_ID")
  elif [ -n "$ORG_ID" ]; then
    CREATE_ARGS+=("--organization=$ORG_ID")
  fi

  gcloud projects create "${CREATE_ARGS[@]}"
fi

gcloud config set project "$PROJECT_ID"

if [ -z "$BILLING_ACCOUNT_ID" ]; then
  echo
  echo "Nenhum BILLING_ACCOUNT_ID informado."
  echo "Contas de billing visíveis para seu usuário:"
  gcloud billing accounts list || true
  echo
  echo "Para vincular billing, rode novamente com:"
  echo "export BILLING_ACCOUNT_ID=XXXXXX-XXXXXX-XXXXXX"
  echo "./scripts/create_gcp_project.sh"
  exit 0
fi

echo "Vinculando billing ao projeto..."
gcloud billing projects link "$PROJECT_ID" --billing-account "$BILLING_ACCOUNT_ID"

echo "Habilitando APIs necessárias..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  iam.googleapis.com \
  secretmanager.googleapis.com

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
COMPUTE_SA="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

echo "Concedendo permissão Vertex AI User à service account padrão do Cloud Run..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:$COMPUTE_SA" \
  --role="roles/aiplatform.user" \
  --quiet >/dev/null

cat <<EOF

Projeto pronto para deploy.

Agora rode:

export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"
export REGION="$REGION"
export SERVICE_NAME="fin-bigdata"
export GEMINI_MODEL="gemini-2.5-flash"
export ALLOW_UNAUTHENTICATED="true"

./scripts/deploy_cloud_run.sh

EOF
