# Fin BigData — Cartola Data Workspace

Projeto 100% baseado em **Google Cloud**, **Vertex AI**, **Gemini**, **Google Cloud Storage** e integração com **Dremio via PAT do próprio usuário**.

> Decisão arquitetural: **não existe API Claude neste projeto**. Não haverá `anthropic`, chave Claude, fallback Claude, tool Claude ou qualquer dependência operacional da Anthropic. O agente oficial do projeto é Gemini via Vertex AI.

## Objetivo

Construir uma bancada analítica assistida por IA para trabalhar com:

- planilhas grandes locais ou em `gs://`;
- arquivos CSV, XLSX e Parquet;
- dados corporativos já publicados no Dremio;
- consultas SQL guiadas por agente;
- análise com evidência, sem jogar arquivo bruto inteiro no modelo.

A IA não analisa arquivo bruto diretamente. A IA orquestra consultas sobre dados estruturados.

## Status atual: spike técnico

Este repositório ainda é um **spike técnico**, não o produto final.

Um spike é um experimento curto para reduzir incerteza antes de investir na construção do MVP. A meta aqui não é ter UX final, autenticação corporativa completa ou arquitetura definitiva. A meta é provar que o núcleo técnico funciona.

Fluxo de evolução esperado:

```text
Ideia → Spike → MVP → Produto interno
```

### Questões que este spike precisa responder

Antes de evoluir para MVP, precisamos validar objetivamente:

1. **Gemini via Vertex AI consegue orquestrar tools com consistência?**
   - O agente chama `list_tables`, `describe_table`, `sample_rows` e `run_sql` na ordem certa?
   - Ele corrige SQL quando recebe erro?
   - Ele evita inventar colunas?

2. **DuckDB é suficiente para consultar planilhas locais e arquivos em GCS?**
   - CSV, XLSX e Parquet carregam bem?
   - Arquivos grandes continuam performáticos?
   - O suporte a `gs://` via `httpfs` é estável no ambiente GCP?

3. **Dremio via PAT funciona bem como engine corporativa?**
   - O app lista apenas datasets que o usuário pode acessar?
   - O PAT do usuário herda as permissões corretamente?
   - As queries via REST API retornam rápido o bastante?

4. **A interface `AnalyticsEngine` segura os dois mundos?**
   - O mesmo agente consegue consultar DuckDB e Dremio sem mudar lógica?
   - Os retornos de `QueryResult` e `TableInfo` são suficientes?
   - O contrato atual suporta outras engines no futuro, se necessário?

5. **O agente gera SQL útil sem depender de contexto manual excessivo?**
   - Ele entende schemas a partir das tools?
   - Ele usa amostras antes de assumir significado de coluna?
   - Ele entrega resposta com SQL e evidência?

6. **O modo Dremio continua 100% alinhado à arquitetura Google Cloud?**
   - Dremio entra apenas como engine de dados.
   - O raciocínio e a resposta final continuam com Gemini via Vertex AI.
   - Não existe chamada para Claude, Anthropic ou outro provedor LLM.

7. **Quais pontos bloqueiam a ida para MVP?**
   - Falta persistência de metadata?
   - Falta histórico de conversas?
   - Falta controle de custo por usuário?
   - Falta modo assistido para joins?
   - Falta deploy em Cloud Run?

### Critério para sair de spike e virar MVP

Este projeto começa a virar MVP quando conseguirmos demonstrar:

- um usuário consegue carregar uma planilha e perguntar sobre ela;
- um usuário consegue conectar no Dremio com PAT e consultar datasets permitidos;
- Gemini chama tools corretamente e responde com evidência;
- o mesmo agente funciona sobre DuckDB e Dremio;
- o sistema não depende de Claude ou APIs externas fora do desenho GCP;
- existe plano claro para Fastify, Cloud Run, Cloud SQL e modo assistido de joins.

## Stack oficial

| Camada | Decisão |
|--------|---------|
| Cloud | Google Cloud Platform |
| LLM | Gemini via Vertex AI |
| SDK LLM | `google-genai` |
| Autenticação LLM | Application Default Credentials |
| Storage | Google Cloud Storage |
| Engine planilhas | DuckDB |
| Processamento futuro | Polars / Cloud Run Jobs |
| Engine corporativa | Dremio SQL Engine |
| Auth Dremio | Personal Access Token do usuário |
| Backend futuro | Fastify + TypeScript |
| Metadata futura | Cloud SQL PostgreSQL |

## O que este projeto NÃO usa

- Não usa Claude API.
- Não usa Anthropic SDK.
- Não usa API key da Anthropic.
- Não usa OpenAI API neste spike.
- Não usa BigQuery no MVP.
- Não acessa S3 corporativo diretamente.
- Não usa service user único do Dremio no MVP.

## Arquitetura

```text
                    ┌──────────────────────┐
                    │   AGENTE GEMINI      │
                    │  Vertex AI / GCP     │
                    └──────────┬───────────┘
                               │
                    AnalyticsEngine (interface)
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
     ┌─────────────────────┐       ┌─────────────────────┐
     │ SpreadsheetEngine   │       │  DremioEngine       │
     │ DuckDB + GCS        │       │  REST API + PAT     │
     └─────────────────────┘       └─────────────────────┘
```

A interface `AnalyticsEngine` padroniza o acesso às engines. O agente Gemini não precisa saber se está consultando DuckDB ou Dremio. Ele chama ferramentas comuns como `list_tables`, `describe_table`, `sample_rows` e `run_sql`.

## Modos de uso

### Modo 1 — Planilha local

O usuário aponta para um arquivo local. A engine carrega o arquivo no DuckDB e o agente Gemini passa a consultar a tabela por SQL.

```text
python main.py
Opção [1/2]: 1
Caminho do arquivo: /caminho/para/vendas.xlsx
Nome da tabela [vendas]:
```

### Modo 2 — Planilha no Google Cloud Storage

O usuário aponta para um arquivo no GCS.

```text
Caminho do arquivo: gs://meu-bucket/vendas/2025-q4.parquet
```

O DuckDB usa suporte a GCS via extensão `httpfs`.

### Modo 3 — Dremio via PAT

O usuário informa o host do Dremio e seu próprio Personal Access Token.

```text
Opção [1/2]: 2
Host do Dremio: https://dremio.empresa.com
Personal Access Token: ********
É Dremio Cloud? [s/N]: n
Workspaces para listar: Comercial,Financeiro
```

As permissões são herdadas do próprio Dremio. O app não cria uma camada paralela de autorização.

## Setup GCP

### 1. Instalar e autenticar gcloud

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project SEU_PROJECT_ID
```

### 2. Habilitar Vertex AI

```bash
gcloud services enable aiplatform.googleapis.com
```

### 3. Variáveis de ambiente

```bash
export GOOGLE_CLOUD_PROJECT="seu-projeto-id"
export GOOGLE_CLOUD_LOCATION="us-central1"

# Modelo padrão do agente
export GEMINI_MODEL="gemini-2.5-flash"

# Dremio, se quiser evitar digitar no terminal
export DREMIO_HOST="https://dremio.empresa.com"
export DREMIO_PAT="seu_pat"

# Opcional para GCS via DuckDB
export GCS_HMAC_KEY_ID="GOOG..."
export GCS_HMAC_SECRET="..."
```

## Dependências Python

```bash
pip install -r requirements.txt
```

## Rodar

```bash
python main.py
```

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---------|------------------|
| `main.py` | Entrada CLI do spike, escolha entre planilha e Dremio |
| `config.py` | Contratos comuns: `AnalyticsEngine`, `QueryResult`, `TableInfo` |
| `spreadsheet_engine.py` | Engine DuckDB para arquivos locais ou GCS |
| `dremio_engine.py` | Engine Dremio via REST API e PAT do usuário |
| `agent.py` | Agente Gemini via Vertex AI com function calling |
| `requirements.txt` | Dependências Python do spike |

## Ferramentas do agente

O agente Gemini opera com function calling e pode chamar:

- `list_tables()` para descobrir tabelas disponíveis;
- `describe_table(table_name)` para ler schema;
- `sample_rows(table_name)` para entender amostras reais;
- `run_sql(query)` para executar consultas SQL.

Regras importantes:

1. O agente deve listar tabelas antes de responder.
2. O agente deve descrever e amostrar tabelas antes de escrever SQL.
3. O agente deve usar SQL agregado ou filtrado, nunca trazer milhões de linhas para o chat.
4. O agente deve mostrar evidência e SQL usado.
5. O agente deve perguntar quando não souber o significado de uma coluna.

## Decisão sobre Dremio

Mesmo no modo Dremio, o projeto continua 100% Google Cloud na camada de IA e aplicação.

O Dremio entra como engine corporativa de dados. O agente continua sendo Gemini via Vertex AI.

Fluxo:

1. Usuário informa PAT do Dremio.
2. App valida acesso.
3. App lista datasets permitidos.
4. Gemini decide quais tools chamar.
5. Queries são executadas no Dremio.
6. A resposta final é gerada pelo Gemini com evidências.

## Custos esperados

Com `gemini-2.5-flash`, uma conversa típica de 5 a 10 turnos tende a custar centavos ou menos, dependendo de tokens, schemas e resultados retornados.

Se trocar para `gemini-2.5-pro`, o custo sobe, mas pode valer para análises mais complexas.

## Próximos passos

1. Validar o spike localmente com `GOOGLE_CLOUD_PROJECT` e ADC.
2. Testar modo planilha com CSV/XLSX.
3. Testar modo Dremio com PAT real.
4. Revisar código para remover qualquer resquício conceitual de Claude.
5. Evoluir para Fastify + TypeScript no backend.
6. Adicionar modo assistido para joins.
7. Subir workers e API no Cloud Run.
8. Persistir metadata em Cloud SQL PostgreSQL.

## Troubleshooting

**`gcloud: command not found`**

Instalar Google Cloud SDK.

**`Could not automatically determine credentials`**

Rodar:

```bash
gcloud auth application-default login
```

**`PERMISSION_DENIED: Vertex AI API has not been used`**

Rodar:

```bash
gcloud services enable aiplatform.googleapis.com
```

**`PERMISSION_DENIED on project`**

Confirmar `GOOGLE_CLOUD_PROJECT` e permissão `Vertex AI User`.

**Erro ao ler `gs://...`**

Configurar HMAC keys ou garantir que a conta/ambiente tenha permissão no bucket.

## Princípio do projeto

> O agente não substitui o analista. Ele vira o copiloto operacional da bancada analítica.

Sem Claude. Sem gambiarra multi-cloud no MVP. Sem jogar planilha gigante dentro do prompt. É GCP + Gemini + dados estruturados.