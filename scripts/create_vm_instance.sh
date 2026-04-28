#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
ZONE="${ZONE:-us-central1-a}"
REGION="${REGION:-us-central1}"
VM_NAME="${VM_NAME:-fin-bigdata-vm}"
MACHINE_TYPE="${MACHINE_TYPE:-e2-medium}"
BOOT_DISK_SIZE="${BOOT_DISK_SIZE:-30GB}"
BOOT_DISK_TYPE="${BOOT_DISK_TYPE:-pd-balanced}"
IMAGE_FAMILY="${IMAGE_FAMILY:-ubuntu-2204-lts}"
IMAGE_PROJECT="${IMAGE_PROJECT:-ubuntu-os-cloud}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-fin-bigdata-vm-sa}"
REPO_URL="${REPO_URL:-https://github.com/gcartola/fin-bigdata.git}"
ALLOW_HTTP_8501="${ALLOW_HTTP_8501:-true}"

if [ -z "$PROJECT_ID" ]; then
  echo "Erro: nenhum projeto ativo encontrado."
  echo "Use: gcloud config set project SEU_PROJECT_ID"
  echo "ou: export GOOGLE_CLOUD_PROJECT=SEU_PROJECT_ID"
  exit 1
fi

printf '\n== Criar VM para Fin BigData ==\n'
printf 'Projeto:      %s\n' "$PROJECT_ID"
printf 'Zona:         %s\n' "$ZONE"
printf 'VM:           %s\n' "$VM_NAME"
printf 'Machine type: %s\n' "$MACHINE_TYPE"
printf 'Disco:        %s %s\n' "$BOOT_DISK_TYPE" "$BOOT_DISK_SIZE"
printf 'Service acct: %s\n\n' "$SERVICE_ACCOUNT_NAME"

gcloud config set project "$PROJECT_ID"

echo "Habilitando APIs necessárias no projeto existente..."
gcloud services enable \
  compute.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  iam.googleapis.com

SA_EMAIL="$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
  echo "Service account já existe: $SA_EMAIL"
else
  echo "Criando service account da VM: $SA_EMAIL"
  gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --display-name="Fin BigData VM service account"
fi

echo "Garantindo permissões mínimas para Vertex AI e deploy Cloud Run..."
for ROLE in \
  roles/aiplatform.user \
  roles/run.admin \
  roles/cloudbuild.builds.editor \
  roles/artifactregistry.admin \
  roles/iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="$ROLE" \
    --quiet >/dev/null
 done

if gcloud compute instances describe "$VM_NAME" --zone "$ZONE" >/dev/null 2>&1; then
  echo "VM já existe: $VM_NAME"
else
  echo "Criando VM..."
  gcloud compute instances create "$VM_NAME" \
    --zone "$ZONE" \
    --machine-type "$MACHINE_TYPE" \
    --boot-disk-size "$BOOT_DISK_SIZE" \
    --boot-disk-type "$BOOT_DISK_TYPE" \
    --image-family "$IMAGE_FAMILY" \
    --image-project "$IMAGE_PROJECT" \
    --service-account "$SA_EMAIL" \
    --scopes "https://www.googleapis.com/auth/cloud-platform" \
    --tags "fin-bigdata"
fi

if [ "$ALLOW_HTTP_8501" = "true" ]; then
  if gcloud compute firewall-rules describe allow-fin-bigdata-streamlit >/dev/null 2>&1; then
    echo "Firewall allow-fin-bigdata-streamlit já existe."
  else
    echo "Criando regra de firewall para teste Streamlit na porta 8501..."
    gcloud compute firewall-rules create allow-fin-bigdata-streamlit \
      --allow tcp:8501 \
      --target-tags fin-bigdata \
      --description "Allow Streamlit spike access on port 8501" \
      --direction INGRESS \
      --priority 1000
  fi
fi

EXTERNAL_IP="$(gcloud compute instances describe "$VM_NAME" --zone "$ZONE" --format='value(networkInterfaces[0].accessConfigs[0].natIP)')"

cat <<EOF

VM pronta.

Nome:       $VM_NAME
Zona:       $ZONE
IP externo: $EXTERNAL_IP

Para acessar via SSH:

gcloud compute ssh $VM_NAME --zone $ZONE

Dentro da VM, rode:

git clone $REPO_URL
cd fin-bigdata
chmod +x scripts/bootstrap_gcloud_vm.sh
./scripts/bootstrap_gcloud_vm.sh

Depois edite .env, carregue variáveis e teste:

nano .env
set -a
source .env
set +a
source .venv/bin/activate
streamlit run app.py --server.port 8501 --server.address 0.0.0.0

URL de teste local da VM:

http://$EXTERNAL_IP:8501

Para publicar no Cloud Run depois:

chmod +x scripts/deploy_cloud_run.sh
./scripts/deploy_cloud_run.sh

EOF
