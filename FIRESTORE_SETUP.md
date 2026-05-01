# Firestore setup

Para a persistência real de conversas, o projeto precisa ter um database Firestore em modo Native.

No Cloud Shell, rode:

```bash
gcloud config set project fin-bigdata

gcloud services enable firestore.googleapis.com cloudresourcemanager.googleapis.com --project fin-bigdata

gcloud firestore databases create \
  --database='(default)' \
  --location=southamerica-east1 \
  --type=firestore-native \
  --project=fin-bigdata
```

Se o database já existir, o comando de criação pode retornar erro de já existente. Nesse caso, siga com o deploy normalmente.

Depois rode o deploy do Cloud Run.

## Validação

1. Entre no app com o PAT.
2. Conecte uma fonte Dremio ou Planilha.
3. Faça a primeira pergunta.
4. A conversa deve aparecer no sidebar.
5. Saia/troque PAT.
6. Entre novamente com um PAT do mesmo usuário.
7. A conversa deve reaparecer pelo mesmo e-mail/user_id.
