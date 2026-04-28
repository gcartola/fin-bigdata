#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-fin-bigdata}"
REGION="${REGION:-us-central1}"
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
ALLOW_UNAUTHENTICATED="${ALLOW_UNAUTHENTICATED:-true}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"

if [ -z "$PROJECT_ID" ]; then
  echo "Erro: GOOGLE_CLOUD_PROJECT não definido e nenhum projeto ativo no gcloud."
  echo "Use: export GOOGLE_CLOUD_PROJECT=seu-projeto-id"
  exit 1
fi

printf '\n== Deploy Cloud Run ==\n'
printf 'Projeto: %s\n' "$PROJECT_ID"
printf 'Serviço: %s\n' "$SERVICE_NAME"
printf 'Região:  %s\n' "$REGION"
printf 'Modelo:  %s\n\n' "$GEMINI_MODEL"

gcloud config set project "$PROJECT_ID"

echo "Habilitando APIs necessárias..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com

AUTH_FLAG="--no-allow-unauthenticated"
if [ "$ALLOW_UNAUTHENTICATED" = "true" ]; then
  AUTH_FLAG="--allow-unauthenticated"
fi

echo "Implantando no Cloud Run via source deploy..."
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,GEMINI_MODEL=$GEMINI_MODEL" \
  $AUTH_FLAG

SERVICE_URL="$(gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" \
  --format='value(status.address.url)')"

printf '\nDeploy concluído.\n'
printf 'URL:\n%s\n' "$SERVICE_URL"
