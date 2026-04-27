# Cartola Data Workspace — Spike (Stack GCP/Vertex AI)

Versão 100% Google Cloud do spike. Mesmo agente, mesmas tools, agora rodando no **Gemini via Vertex AI** com suporte nativo a **Google Cloud Storage**.

## Diferenças vs spike anterior (Claude)

| Aspecto | Spike Claude | Spike GCP/Vertex (este) |
|---------|--------------|-------------------------|
| LLM | Claude (API direta) | Gemini 2.5 Flash via Vertex AI |
| SDK | `anthropic` | `google-genai` (novo, GA) |
| Autenticação LLM | API key | Application Default Credentials |
| Storage de planilha | Local apenas | Local **ou** `gs://` (GCS) |
| Function calling | `tools=[]` no formato Claude | `Tool(function_declarations=[...])` Gemini |
| Custo | Pago direto pra Anthropic | Sai dos créditos GCP |

## Arquitetura

```text
                    ┌──────────────────────┐
                    │     AGENTE           │
                    │ (Gemini via Vertex)  │
                    └──────────┬───────────┘
                               │
                    AnalyticsEngine (interface)
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
     ┌─────────────────────┐       ┌─────────────────────┐
     │ SpreadsheetEngine   │       │  DremioEngine       │
     │ (DuckDB + GCS)      │       │  (API REST + PAT)   │
     └─────────────────────┘       └─────────────────────┘
```

A interface `AnalyticsEngine` continua a mesma. Trocar Claude por Gemini só mexeu em `agent.py`. Strategy pattern funciona dos dois lados.

## Setup

### 1. Pré-requisitos GCP

```bash
# Instalar gcloud CLI (se ainda não tiver)
# https://cloud.google.com/sdk/docs/install

# Login
gcloud auth login
gcloud auth application-default login

# Definir projeto (use o seu projeto com créditos)
gcloud config set project SEU_PROJECT_ID

# Habilitar Vertex AI API
gcloud services enable aiplatform.googleapis.com
```

### 2. Variáveis de ambiente

```bash
# Obrigatório
export GOOGLE_CLOUD_PROJECT="seu-projeto-id"

# Opcional (default: us-central1)
export GOOGLE_CLOUD_LOCATION="us-central1"

# Opcional: trocar o modelo (default: gemini-2.5-flash)
export GEMINI_MODEL="gemini-2.5-pro"  # mais inteligente, mais caro
# ou
export GEMINI_MODEL="gemini-3-flash-preview"  # mais novo

# Para Dremio (pode digitar interativamente também)
export DREMIO_HOST="https://dremio.empresa.com"
export DREMIO_PAT="seu_pat"

# Para arquivos no GCS via DuckDB (opcional)
# Crie HMAC keys em: Cloud Console > Storage > Settings > Interoperability
export GCS_HMAC_KEY_ID="GOOG..."
export GCS_HMAC_SECRET="..."
```

### 3. Dependências Python

```bash
pip install google-genai duckdb requests polars
```

### 4. Rodar

```bash
python main.py
```

## Modos de uso

### Modo 1 — Planilha local

```text
$ python main.py
Opção [1/2]: 1
Caminho do arquivo: /caminho/para/vendas.xlsx
  Nome da tabela [vendas]:
  ✓ 'vendas': 250,000 linhas, 12 colunas
Caminho do arquivo: <ENTER>

Agente pronto. Engine: DuckDB
Modelo: gemini-2.5-flash (via Vertex AI)

💬 Você: qual região vendeu mais no Q4?
🤔 Pensando...
  [tool] list_tables({})
  [tool] describe_table({"table_name": "vendas"})
  [tool] sample_rows({"table_name": "vendas"})
  [tool] run_sql({"query": "SELECT regiao, SUM(valor) ..."})

🤖 Agente:
A região Sudeste liderou no Q4 com R$ 12.4M, seguida do Sul com R$ 8.1M...
```

### Modo 2 — Planilha no GCS

```text
Caminho do arquivo: gs://meu-bucket/vendas/2025-q4.parquet
```

### Modo 3 — Dremio

```text
Opção [1/2]: 2
Host do Dremio: https://dremio.empresa.com
Personal Access Token: ********
É Dremio Cloud? [s/N]: n
Workspaces para listar: Comercial,Financeiro
  ✓ Conectado. 47 tabelas visíveis.

💬 Você: vendas vs inadimplência por empreendimento
```

## Estrutura de arquivos

| Arquivo | O que tem | Mudou vs spike Claude? |
|---------|-----------|------------------------|
| `config.py` | Interface `AnalyticsEngine` | Não |
| `spreadsheet_engine.py` | DuckDB + suporte GCS | Sim (adicionou httpfs/GCS) |
| `dremio_engine.py` | Dremio REST API | Não |
| `agent.py` | Loop Gemini + tools | **Sim — reescrito para Gemini** |
| `main.py` | Terminal interativo | Sim (validação ADC e GOOGLE_CLOUD_PROJECT) |

## Custos esperados

Com `gemini-2.5-flash` (modelo padrão), uma conversa típica de 5-10 turnos custa **menos de USD 0.01**. Seus créditos GCP devem durar muito tempo nesse tier.

Se trocar para `gemini-2.5-pro`, custo é ~10x maior mas a qualidade do SQL gerado também sobe (vale para queries mais complexas).

## Próximos passos depois de validar

1. **Subir esse spike pra Cloud Run** (deploy serverless, fica acessível pra time)
2. **Trocar terminal por Streamlit** (Cloud Run hospeda Streamlit também)
3. **Adicionar Cloud SQL** pra persistir conversas e enriquecimento de metadados
4. **Adicionar BigQuery como terceira engine** (se um dia precisar — basta criar `bigquery_engine.py`)
5. **Service Account dedicada** em vez de ADC pessoal (pra rodar em produção)

## Troubleshooting

**`gcloud: command not found`** → instalar Google Cloud SDK

**`Could not automatically determine credentials`** → rodar `gcloud auth application-default login`

**`PERMISSION_DENIED: Vertex AI API has not been used`** → habilitar a API: `gcloud services enable aiplatform.googleapis.com`

**`PERMISSION_DENIED on project XXX`** → confirmar que `GOOGLE_CLOUD_PROJECT` está com o ID correto e que sua conta tem permissão `Vertex AI User`

**Erro ao ler `gs://...`** → configurar HMAC keys ou fazer login com conta que tem acesso ao bucket
