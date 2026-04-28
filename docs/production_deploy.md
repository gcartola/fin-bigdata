# Fin BigData — Deploy de Produção

Este runbook leva o app para uma arquitetura de produto:

- Cloud Run como compute stateless
- GCS para upload de arquivos grandes
- Secret Manager para credenciais
- HTTPS via Cloud Run `.run.app` inicialmente
- Load Balancer HTTPS para domínio próprio
- Cloudflare Tunnel como exposição temporária ou alternativa operacional

## 1. Variáveis base

```bash
export GOOGLE_CLOUD_PROJECT="SEU_PROJECT_ID"
export REGION="us-central1"
export SERVICE_NAME="fin-bigdata"
export GEMINI_MODEL="gemini-2.5-flash"
export GCS_UPLOAD_BUCKET="${GOOGLE_CLOUD_PROJECT}-${SERVICE_NAME}-uploads"
export DREMIO_HOST="https://app.dremio.cloud"
export DREMIO_PROJECT_ID="SEU_DREMIO_PROJECT_ID"
```

## 2. APIs necessárias

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  iamcredentials.googleapis.com
```

## 3. Secret Manager

Crie o secret do PAT de serviço apenas se quiser disponibilizar um token corporativo no servidor.
O app também permite que cada analista informe o próprio PAT na UI.

```bash
echo -n "SEU_PAT_DREMIO" | gcloud secrets create DREMIO_PAT \
  --data-file=- \
  --replication-policy="automatic"
```

Para atualizar:

```bash
echo -n "NOVO_PAT_DREMIO" | gcloud secrets versions add DREMIO_PAT --data-file=-
```

## 4. Bucket GCS para uploads grandes

```bash
gsutil mb -p "$GOOGLE_CLOUD_PROJECT" -l "$REGION" "gs://${GCS_UPLOAD_BUCKET}"
```

Configure CORS para permitir PUT via signed URL no browser:

```bash
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

gsutil cors set /tmp/fin-bigdata-cors.json "gs://${GCS_UPLOAD_BUCKET}"
```

Em produção fechada, troque `origin: ["*"]` pelo domínio final, por exemplo `https://fin.cartolab.co`.

## 5. Deploy Cloud Run

Use o script:

```bash
chmod +x scripts/deploy_cloud_run.sh
./scripts/deploy_cloud_run.sh
```

O script faz:

- habilitação de APIs
- criação/configuração do bucket de upload
- configuração de CORS
- deploy via `gcloud run deploy --source .`
- bind opcional do Secret Manager se `DREMIO_PAT` existir

A URL final `.run.app` aparece ao final do deploy.

## 6. Permissões mínimas do runtime

Identifique a service account do Cloud Run:

```bash
gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" \
  --format='value(spec.template.spec.serviceAccountName)'
```

Se estiver usando a service account default do Compute, considere criar uma dedicada:

```bash
gcloud iam service-accounts create fin-bigdata-run-sa \
  --display-name="Fin BigData Cloud Run runtime"
```

Permissões recomendadas:

```bash
SA="fin-bigdata-run-sa@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:${SA}" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:${SA}" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:${SA}" \
  --role="roles/iam.serviceAccountTokenCreator"

gcloud secrets add-iam-policy-binding DREMIO_PAT \
  --member="serviceAccount:${SA}" \
  --role="roles/secretmanager.secretAccessor"
```

Depois faça novo deploy passando:

```bash
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --service-account "$SA" \
  --allow-unauthenticated \
  --port 8080
```

`roles/iam.serviceAccountTokenCreator` é necessário para gerar signed URLs V4 quando o runtime usa credenciais de service account gerenciadas.

## 7. Upload grande via GCS

Fluxo implementado no app:

```text
Streamlit gera signed URL
Browser faz PUT direto para GCS
App registra o gs://...
DuckDB lê o arquivo via httpfs/GCS
```

Observação: o upload direto usa um componente HTML/JS dentro do Streamlit. Depois que o upload terminar, clique em `Usar arquivo enviado`.

## 8. Load Balancer HTTPS para domínio próprio

Não usar Cloud Run Domain Mapping. Use External Application Load Balancer com serverless NEG.

Variáveis:

```bash
export DOMAIN="fin.cartolab.co"
export LB_NAME="fin-bigdata-lb"
export NEG_NAME="fin-bigdata-neg"
export BACKEND_NAME="fin-bigdata-backend"
export CERT_NAME="fin-bigdata-cert"
export URL_MAP_NAME="fin-bigdata-url-map"
export HTTPS_PROXY_NAME="fin-bigdata-https-proxy"
export IP_NAME="fin-bigdata-ip"
export FORWARDING_RULE_NAME="fin-bigdata-https-rule"
```

Crie NEG serverless apontando para Cloud Run:

```bash
gcloud compute network-endpoint-groups create "$NEG_NAME" \
  --region "$REGION" \
  --network-endpoint-type=serverless \
  --cloud-run-service="$SERVICE_NAME"
```

Backend service:

```bash
gcloud compute backend-services create "$BACKEND_NAME" \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED

gcloud compute backend-services add-backend "$BACKEND_NAME" \
  --global \
  --network-endpoint-group="$NEG_NAME" \
  --network-endpoint-group-region="$REGION"
```

IP global:

```bash
gcloud compute addresses create "$IP_NAME" --global

gcloud compute addresses describe "$IP_NAME" --global --format='value(address)'
```

Aponte o DNS `A` de `fin.cartolab.co` para esse IP.

Certificado gerenciado:

```bash
gcloud compute ssl-certificates create "$CERT_NAME" \
  --domains="$DOMAIN" \
  --global
```

URL map, proxy e forwarding rule:

```bash
gcloud compute url-maps create "$URL_MAP_NAME" \
  --default-service="$BACKEND_NAME"

gcloud compute target-https-proxies create "$HTTPS_PROXY_NAME" \
  --ssl-certificates="$CERT_NAME" \
  --url-map="$URL_MAP_NAME"

gcloud compute forwarding-rules create "$FORWARDING_RULE_NAME" \
  --global \
  --load-balancing-scheme=EXTERNAL_MANAGED \
  --address="$IP_NAME" \
  --target-https-proxy="$HTTPS_PROXY_NAME" \
  --ports=443
```

A emissão do certificado pode levar alguns minutos após o DNS apontar corretamente.

## 9. Cloudflare Tunnel temporário

Opção A: túnel apontando para a URL do Cloud Run:

```bash
cloudflared tunnel create fin-bigdata
cloudflared tunnel route dns fin-bigdata fin.cartolab.co
```

`~/.cloudflared/config.yml`:

```yaml
tunnel: fin-bigdata
credentials-file: /home/USER/.cloudflared/TUNNEL_ID.json

ingress:
  - hostname: fin.cartolab.co
    service: https://fin-bigdata-xxxxx-uc.a.run.app
    originRequest:
      noTLSVerify: false
  - service: http_status:404
```

Rodar:

```bash
cloudflared tunnel run fin-bigdata
```

Opção B: túnel temporário para a VM, enquanto Cloud Run/LB estabiliza:

```yaml
ingress:
  - hostname: fin.cartolab.co
    service: http://localhost:8501
  - service: http_status:404
```

## 10. Checklist de aceite

- Cloud Run responde em URL `.run.app`
- Campo PAT não vem preenchido para usuário comum
- Se `DREMIO_PAT` existir no Secret Manager, aparece opção de PAT de serviço
- Upload grande usa signed URL e arquivo cai no GCS
- DuckDB carrega `gs://...`
- Query via agente funciona
- Download CSV/Excel segue funcionando
- Domínio pronto para apontar via Load Balancer
