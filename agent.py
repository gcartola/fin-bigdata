import json
import os
import re
from collections.abc import Callable

from google import genai
from google.genai import types

from config import AnalyticsEngine


def build_tools() -> list[types.Tool]:
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="list_tables",
                    description=(
                        "Lista todas as tabelas disponíveis na engine atual. "
                        "Use isso PRIMEIRO quando o usuário fizer uma pergunta."
                    ),
                    parameters=types.Schema(type=types.Type.OBJECT, properties={}),
                ),
                types.FunctionDeclaration(
                    name="describe_table",
                    description=(
                        "Retorna o schema (colunas, tipos) e contagem de linhas de uma tabela. "
                        "Use ANTES de escrever qualquer SQL."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "table_name": types.Schema(
                                type=types.Type.STRING,
                                description="Nome ou caminho completo da tabela (use exatamente como veio em list_tables)",
                            )
                        },
                        required=["table_name"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="sample_rows",
                    description=(
                        "Retorna 5 linhas de amostra de uma tabela. Use para entender "
                        "o conteúdo real (formatos de data, valores típicos)."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "table_name": types.Schema(
                                type=types.Type.STRING,
                                description="Nome ou caminho da tabela",
                            )
                        },
                        required=["table_name"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="run_sql",
                    description=(
                        "Executa uma query SQL e retorna o resultado. "
                        "Sempre prefira queries que agregam ou filtram. "
                        "Se der erro, leia a mensagem e tente corrigir."
                    ),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "query": types.Schema(
                                type=types.Type.STRING,
                                description="SQL completo para executar",
                            )
                        },
                        required=["query"],
                    ),
                ),
            ]
        )
    ]


def sanitize_markdown(text: str) -> str:
    """Remove pequenos vazamentos de HTML que aparecem como texto no chat.

    O Streamlit renderiza markdown, mas o modelo às vezes devolve tags HTML
    literais como <hr>. Em vez de deixar isso poluir a conversa persistida,
    normalizamos para markdown limpo.
    """
    if not text:
        return text
    cleaned = text
    cleaned = re.sub(r"(?i)<\s*hr\s*/?\s*>", "\n---\n", cleaned)
    cleaned = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", cleaned)
    cleaned = re.sub(r"(?i)</?p\s*>", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def system_instruction(engine: AnalyticsEngine) -> str:
    return f"""Você é um analista de dados sênior conversando com um colega via chat.

Sua engine de query atual: {engine.engine_name}
Dialeto SQL: {engine.sql_dialect}

REGRAS DE TRABALHO:

1. SEMPRE comece com list_tables para descobrir o que existe.
2. ANTES de escrever SQL, use describe_table e sample_rows nas tabelas relevantes.
   Não chute nomes de colunas ou formatos de dados.
3. Escreva SQL que AGREGA ou FILTRA. Nunca traga 1M linhas pro chat.
   Use LIMIT, GROUP BY, agregações.
4. Se uma query der erro, LEIA a mensagem, corrija e tente de novo.
   Não desista na primeira tentativa.
5. Ao apresentar o resultado:
   - Explique em português o que os números significam
   - Mostre o SQL que você usou (transparência)
   - Sugira próximas perguntas que o usuário poderia fazer
6. Se você não tem certeza sobre o significado de uma coluna, PERGUNTE
   antes de inventar uma interpretação.
7. Quando o usuário pedir download, exportação, tabela completa ou arquivo,
   gere uma consulta SQL que retorne o resultado completo filtrado. Não responda
   que não consegue gerar arquivo. O frontend disponibilizará os botões de
   download. Use LIMIT apenas quando o usuário pedir amostra ou preview.
8. Se houver apenas uma view/tabela disponível após list_tables, use diretamente
   essa view/tabela. Evite explorar catálogo inteiro ou procurar outras tabelas.
9. Para busca por contrato, CPF, nome ou identificador específico, vá direto no
   filtro da view/tabela selecionada. Não faça varredura ampla se já existe uma
   fonte selecionada.
10. Não use HTML nas respostas. Não use tags como <hr>, <br>, <p> ou similares.
    Use apenas markdown puro.

ESTILO:
- Direto, sem rodeios. Você é colega, não assistente bajulador.
- Português do Brasil.
- Use markdown para tabelas e código.
"""


class Agent:
    def __init__(self, engine: AnalyticsEngine, model: str = "gemini-2.5-flash", project_id: str | None = None, location: str = "us-central1"):
        self.engine = engine
        self.model = model
        self.client = genai.Client(
            vertexai=True,
            project=project_id or os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )
        self.tools = build_tools()
        self.system = system_instruction(engine)
        self.conversation: list[types.Content] = []
        self.last_query_result = None

    def load_history(self, messages: list[dict], max_messages: int = 20) -> None:
        """Reidrata o contexto textual recente salvo fora do processo.

        Não tenta reconstruir tool calls antigas. Para memória operacional, o app
        persiste SQL/resumos como metadados e injeta apenas o histórico textual
        recente no modelo.
        """
        self.conversation = []
        for message in messages[-max_messages:]:
            role = message.get("role")
            content = sanitize_markdown((message.get("content") or "").strip())
            if role not in ("user", "assistant") or not content:
                continue
            self.conversation.append(types.Content(role=role, parts=[types.Part(text=content)]))

    def _tool_label(self, name: str, args: dict) -> str:
        if name == "list_tables":
            return "Listando tabelas/views disponíveis"
        if name == "describe_table":
            return f"Lendo estrutura de `{args.get('table_name', '')}`"
        if name == "sample_rows":
            return f"Buscando amostra de `{args.get('table_name', '')}`"
        if name == "run_sql":
            query = (args.get("query") or "").replace("\n", " ").strip()
            preview = query[:180] + ("..." if len(query) > 180 else "")
            return f"Executando SQL: `{preview}`"
        return f"Executando ferramenta `{name}`"

    def _execute_tool(self, name: str, args: dict) -> str:
        try:
            if name == "list_tables":
                tables = self.engine.list_tables()
                if not tables:
                    return "Nenhuma tabela disponível."
                lines = []
                for t in tables:
                    line = f"- **{t.full_path}**"
                    if t.row_count is not None:
                        line += f" ({t.row_count:,} linhas)"
                    if t.description:
                        line += f" — {t.description}"
                    lines.append(line)
                return "Tabelas disponíveis:\n" + "\n".join(lines)

            if name == "describe_table":
                info = self.engine.describe_table(args["table_name"])
                cols = "\n".join(f"- `{c['name']}` ({c['type']})" for c in info.columns)
                count_str = f"{info.row_count:,} linhas\n" if info.row_count else ""
                return f"**{info.full_path}**\n{count_str}\nColunas:\n{cols}"

            if name == "sample_rows":
                result = self.engine.sample_rows(args["table_name"], n=5)
                return f"Amostra de {result.row_count} linhas:\n\n{result.to_markdown()}"

            if name == "run_sql":
                result = self.engine.run_sql(args["query"])
                self.last_query_result = result
                return (
                    f"Query executada em {result.execution_time_ms}ms. "
                    f"{result.row_count} linhas retornadas.\n\n"
                    f"{result.to_markdown(max_rows=20)}"
                )

            return f"Tool desconhecida: {name}"
        except Exception as e:
            return f"ERRO: {e}"

    def chat(self, user_message: str, progress_callback: Callable[[str], None] | None = None) -> str:
        def emit(message: str):
            print(f"  [status] {message}")
            if progress_callback:
                progress_callback(message)

        self.conversation.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

        max_iterations = 15
        for iteration in range(max_iterations):
            emit(f"🧠 Pensando com o modelo ({iteration + 1}/{max_iterations})")
            response = self.client.models.generate_content(
                model=self.model,
                contents=self.conversation,
                config=types.GenerateContentConfig(system_instruction=self.system, tools=self.tools, temperature=0.2),
            )

            candidate = response.candidates[0]
            content = candidate.content
            self.conversation.append(content)

            function_calls = [part.function_call for part in content.parts if part.function_call is not None]

            if not function_calls:
                final_text = ""
                for part in content.parts:
                    if part.text:
                        final_text += part.text
                final_text = sanitize_markdown(final_text)
                emit("✅ Resposta final pronta")
                return final_text or "[Sem resposta de texto]"

            function_response_parts = []
            for fc in function_calls:
                args = dict(fc.args) if fc.args else {}
                preview = json.dumps(args, ensure_ascii=False)[:160]
                tool_label = self._tool_label(fc.name, args)
                print(f"  [tool] {fc.name}({preview})")
                emit(f"🔧 {tool_label}")
                result_str = self._execute_tool(fc.name, args)
                if result_str.startswith("ERRO:"):
                    emit(f"⚠️ {fc.name} retornou erro; tentando corrigir")
                else:
                    emit(f"✅ {fc.name} concluído")
                function_response_parts.append(
                    types.Part(function_response=types.FunctionResponse(name=fc.name, response={"result": result_str}))
                )

            self.conversation.append(types.Content(role="user", parts=function_response_parts))

        emit("⚠️ Limite de iterações atingido")
        return "[Limite de iterações atingido sem resposta final]"
