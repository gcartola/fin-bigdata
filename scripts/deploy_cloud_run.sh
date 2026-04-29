#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-fin-bigdata}"
REGION="${REGION:-us-central1}"
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
ALLOW_UNAUTHENTICATED="${ALLOW_UNAUTHENTICATED:-true}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-pro}"
UPLOAD_BUCKET="${GCS_UPLOAD_BUCKET:-${PROJECT_ID}-${SERVICE_NAME}-uploads}"
MEMORY="${MEMORY:-2Gi}"
CPU="${CPU:-2}"
TIMEOUT="${TIMEOUT:-900}"
DREMIO_HOST="${DREMIO_HOST:-}"
DREMIO_PROJECT_ID="${DREMIO_PROJECT_ID:-}"

if [ -z "$PROJECT_ID" ]; then
  echo "Erro: GOOGLE_CLOUD_PROJECT não definido e nenhum projeto ativo no gcloud."
  echo "Use: export GOOGLE_CLOUD_PROJECT=seu-projeto-id"
  exit 1
fi

printf '\n== Deploy Cloud Run ==\n'
printf 'Projeto:       %s\n' "$PROJECT_ID"
printf 'Serviço:       %s\n' "$SERVICE_NAME"
printf 'Região:        %s\n' "$REGION"
printf 'Modelo:        %s\n' "$GEMINI_MODEL"
printf 'Upload bucket: %s\n\n' "$UPLOAD_BUCKET"

gcloud config set project "$PROJECT_ID"

echo "Habilitando APIs necessárias..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  iamcredentials.googleapis.com

if ! gsutil ls -b "gs://${UPLOAD_BUCKET}" >/dev/null 2>&1; then
  echo "Criando bucket gs://${UPLOAD_BUCKET}..."
  gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${UPLOAD_BUCKET}"
fi

cat > /tmp/fin-bigdata-cors.json <<'JSON'
[
  {
    "origin": ["*"],
    "method": ["PUT", "GET", "HEAD", "OPTIONS"],
    "responseHeader": ["Content-Type", "x-goog-resumable", "ETag"],
    "maxAgeSeconds": 3600
  }
]
JSON

echo "Configurando CORS do bucket para upload via signed URL..."
gsutil cors set /tmp/fin-bigdata-cors.json "gs://${UPLOAD_BUCKET}"

AUTH_FLAG="--no-allow-unauthenticated"
if [ "$ALLOW_UNAUTHENTICATED" = "true" ]; then
  AUTH_FLAG="--allow-unauthenticated"
fi

ENV_VARS="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,GEMINI_MODEL=$GEMINI_MODEL,GCS_UPLOAD_BUCKET=$UPLOAD_BUCKET"
if [ -n "$DREMIO_HOST" ]; then
  ENV_VARS="$ENV_VARS,DREMIO_HOST=$DREMIO_HOST"
fi
if [ -n "$DREMIO_PROJECT_ID" ]; then
  ENV_VARS="$ENV_VARS,DREMIO_PROJECT_ID=$DREMIO_PROJECT_ID"
fi

SECRET_ARGS=()
if gcloud secrets describe DREMIO_PAT >/dev/null 2>&1; then
  SECRET_ARGS+=(--set-secrets "DREMIO_PAT=DREMIO_PAT:latest")
fi
if gcloud secrets describe GCS_HMAC_KEY_ID >/dev/null 2>&1; then
  SECRET_ARGS+=(--set-secrets "GCS_HMAC_KEY_ID=GCS_HMAC_KEY_ID:latest")
fi
if gcloud secrets describe GCS_HMAC_SECRET >/dev/null 2>&1; then
  SECRET_ARGS+=(--set-secrets "GCS_HMAC_SECRET=GCS_HMAC_SECRET:latest")
fi

echo "Implantando no Cloud Run via source deploy..."
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --port 8080 \
  --memory "$MEMORY" \
  --cpu "$CPU" \
  --timeout "$TIMEOUT" \
  --set-env-vars "$ENV_VARS" \
  "${SECRET_ARGS[@]}" \
  $AUTH_FLAG

SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" \
  --format='value(status.url)')"

printf '\nDeploy concluído.\n'
printf 'URL:\n%s\n' "$SERVICE_URL"
