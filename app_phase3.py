import re
from itertools import combinations

import streamlit as st

import app_entry as entry


def phase3_state():
    entry.phase_state()
    if "relationship_suggestions" not in st.session_state:
        st.session_state.relationship_suggestions = []
    if "source_data_profiles" not in st.session_state:
        st.session_state.source_data_profiles = {}


def normalize_column_name(name: str) -> str:
    value = (name or "").lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    aliases = {
        "num": "numero",
        "nr": "numero",
        "cod": "codigo",
        "id": "codigo",
        "cpfcnpj": "cpf_cnpj",
        "cpf_cnpj_cliente": "cpf_cnpj",
        "cnpj_cpf": "cpf_cnpj",
        "contrato_cliente": "contrato",
        "numero_do_contrato": "numero_contrato",
        "num_contrato": "numero_contrato",
        "nr_contrato": "numero_contrato",
        "codigo_contrato": "numero_contrato",
        "contrato": "numero_contrato",
        "cod_venda_mega": "codigo_venda_mega",
        "codigo_venda": "codigo_venda_mega",
    }
    return aliases.get(value, value)


def token_set(name: str) -> set[str]:
    normalized = normalize_column_name(name)
    return {token for token in normalized.split("_") if token}


def score_column_pair(left_col: str, right_col: str) -> tuple[float, list[str]]:
    left_norm = normalize_column_name(left_col)
    right_norm = normalize_column_name(right_col)
    left_tokens = token_set(left_col)
    right_tokens = token_set(right_col)
    reasons = []
    score = 0.0

    if left_norm == right_norm:
        score += 0.72
        reasons.append("nome normalizado igual")
    elif left_norm in right_norm or right_norm in left_norm:
        score += 0.48
        reasons.append("nome parecido/contido")
    else:
        intersection = left_tokens & right_tokens
        union = left_tokens | right_tokens
        if union:
            overlap = len(intersection) / len(union)
            score += overlap * 0.44
            if intersection:
                reasons.append(f"tokens em comum: {', '.join(sorted(intersection))}")

    key_groups = [
        {"contrato", "numero_contrato"},
        {"cpf", "cnpj", "cpf_cnpj"},
        {"cliente", "codigo_cliente", "cod_cliente"},
        {"venda", "codigo_venda", "codigo_venda_mega"},
        {"empreendimento", "obra", "projeto"},
        {"unidade", "apto", "bloco"},
    ]
    left_joined = "_".join(sorted(left_tokens | {left_norm}))
    right_joined = "_".join(sorted(right_tokens | {right_norm}))
    for group in key_groups:
        if any(term in left_joined for term in group) and any(term in right_joined for term in group):
            score += 0.2
            reasons.append(f"termo de chave provável: {sorted(group)[0]}")
            break

    if left_col == right_col:
        score += 0.08
        reasons.append("nome original igual")

    if any(term in left_norm for term in ["data", "valor", "desc", "nome", "status"]):
        score -= 0.16
        reasons.append("campo pode ser descritivo/medida, validar antes de cruzar")

    score = max(0.0, min(round(score, 2), 0.99))
    return score, reasons or ["similaridade baixa"]


def confidence_label(score: float) -> str:
    if score >= 0.85:
        return "alta"
    if score >= 0.65:
        return "média"
    return "baixa"


def generate_relationship_suggestions(limit: int = 20) -> list[dict]:
    phase3_state()
    sources = st.session_state.get("active_dremio_sources", [])
    if len(sources) < 2:
        return []

    suggestions = []
    for left, right in combinations(sources, 2):
        left_columns = entry.load_columns_for_source(left["path"])
        right_columns = entry.load_columns_for_source(right["path"])
        for left_col in left_columns:
            for right_col in right_columns:
                score, reasons = score_column_pair(left_col, right_col)
                if score < 0.45:
                    continue
                suggestions.append({
                    "left_path": left["path"],
                    "left_name": left["name"],
                    "left_alias": left["alias"],
                    "left_column": left_col,
                    "right_path": right["path"],
                    "right_name": right["name"],
                    "right_alias": right["alias"],
                    "right_column": right_col,
                    "score": score,
                    "confidence": f"auto_{confidence_label(score)}",
                    "reasons": reasons,
                })
    suggestions.sort(key=lambda item: item["score"], reverse=True)
    st.session_state.relationship_suggestions = suggestions[:limit]
    return st.session_state.relationship_suggestions


def quote_identifier(column: str) -> str:
    return '"' + column.replace('"', '""') + '"'


def profile_column(path: str, column: str) -> dict:
    engine = entry.get_dremio_engine_for_metadata()
    if not engine:
        raise RuntimeError("Dremio não conectado.")
    col = quote_identifier(column)
    query = f'''
SELECT
  COUNT(*) AS total_linhas,
  COUNT({col}) AS valores_preenchidos,
  COUNT(DISTINCT {col}) AS valores_distintos,
  MIN(CAST({col} AS VARCHAR)) AS menor_valor_amostra,
  MAX(CAST({col} AS VARCHAR)) AS maior_valor_amostra
FROM {path}
'''.strip()
    result = engine.run_sql(query)
    values = result.rows[0] if result.rows else []
    return {
        "path": path,
        "column": column,
        "total_linhas": values[0] if len(values) > 0 else None,
        "valores_preenchidos": values[1] if len(values) > 1 else None,
        "valores_distintos": values[2] if len(values) > 2 else None,
        "menor_valor_amostra": values[3] if len(values) > 3 else None,
        "maior_valor_amostra": values[4] if len(values) > 4 else None,
    }


def profile_key(path: str, column: str) -> str:
    return f"{path}::{column}"


def save_profile(profile: dict):
    key = profile_key(profile["path"], profile["column"])
    profiles = st.session_state.get("source_data_profiles", {})
    profiles[key] = profile
    st.session_state.source_data_profiles = profiles
    entry.base_app.update_conversation_state(data_profiles=profiles)
    entry.apply_agent_workspace_context()


def add_suggested_relationship(suggestion: dict):
    existing = st.session_state.get("source_relationships", [])
    signature = (
        suggestion.get("left_path"),
        suggestion.get("left_column"),
        suggestion.get("right_path"),
        suggestion.get("right_column"),
    )
    reverse = (
        suggestion.get("right_path"),
        suggestion.get("right_column"),
        suggestion.get("left_path"),
        suggestion.get("left_column"),
    )
    for rel in existing:
        rel_signature = (rel.get("left_path"), rel.get("left_column"), rel.get("right_path"), rel.get("right_column"))
        if rel_signature in (signature, reverse):
            st.info("Esse relacionamento já existe.")
            return
    relationship = {
        **suggestion,
        "reasons": suggestion.get("reasons", []),
    }
    existing.append(relationship)
    st.session_state.source_relationships = existing
    entry.persist_relationships()
    st.success(f"Relacionamento adicionado: {entry.relationship_label(relationship)}")


def render_relationship_suggestions():
    phase3_state()
    st.markdown("#### Sugestões automáticas")
    sources = st.session_state.get("active_dremio_sources", [])
    if len(sources) < 2:
        st.info("Adicione pelo menos duas views para gerar sugestões.")
        return

    st.caption("As sugestões usam similaridade de nomes de colunas e termos de chave prováveis. Use o score como triagem, não como verdade absoluta.")
    if st.button("Gerar sugestões de relacionamento", type="primary", use_container_width=True, key="generate_relationship_suggestions"):
        try:
            suggestions = generate_relationship_suggestions()
            if suggestions:
                st.success(f"Gerei {len(suggestions)} sugestão(ões).")
            else:
                st.warning("Não encontrei sugestões com score mínimo.")
        except Exception as exc:
            st.error(f"Falha ao gerar sugestões: {exc}")

    suggestions = st.session_state.get("relationship_suggestions", [])
    if not suggestions:
        st.caption("Nenhuma sugestão gerada ainda.")
        return

    for idx, suggestion in enumerate(suggestions, start=1):
        score = suggestion["score"]
        st.markdown(f"**{idx}. {suggestion['left_name']}.{suggestion['left_column']} = {suggestion['right_name']}.{suggestion['right_column']}**")
        st.caption(f"Score: {score:.2f} · Confiança: {confidence_label(score)} · Motivos: {'; '.join(suggestion.get('reasons', []))}")
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            if st.button("Usar", key=f"use_suggestion_{idx}"):
                add_suggested_relationship(suggestion)
                st.rerun()
        with col2:
            if st.button("Perfilar", key=f"profile_suggestion_{idx}"):
                try:
                    left_profile = profile_column(suggestion["left_path"], suggestion["left_column"])
                    right_profile = profile_column(suggestion["right_path"], suggestion["right_column"])
                    save_profile(left_profile)
                    save_profile(right_profile)
                    st.success("Perfil das duas colunas calculado.")
                except Exception as exc:
                    st.error(f"Falha ao calcular perfil: {exc}")
        st.divider()


def render_data_profile():
    phase3_state()
    st.markdown("#### Perfil de dados")
    sources = st.session_state.get("active_dremio_sources", [])
    if not sources:
        st.info("Adicione uma fonte para calcular perfil de dados.")
        return

    source_options = {f"{src['name']} · {idx}": src for idx, src in enumerate(sources, start=1)}
    selected_label = st.selectbox("Fonte", list(source_options.keys()), key="profile_source")
    source = source_options[selected_label]
    columns = entry.load_columns_for_source(source["path"])
    column = st.selectbox("Coluna", columns or [""], key="profile_column")

    if st.button("Calcular perfil da coluna", type="primary", use_container_width=True, key="calculate_column_profile"):
        try:
            profile = profile_column(source["path"], column)
            save_profile(profile)
            st.success("Perfil calculado e salvo na conversa.")
        except Exception as exc:
            st.error(f"Falha ao calcular perfil: {exc}")

    profiles = st.session_state.get("source_data_profiles", {})
    if not profiles:
        st.caption("Nenhum perfil salvo ainda.")
        return

    st.markdown("##### Perfis salvos")
    for profile in profiles.values():
        source_name = entry.source_name_from_path(profile.get("path", ""))
        st.markdown(f"**{source_name}.{profile.get('column')}**")
        st.caption(
            f"Linhas: {profile.get('total_linhas')} · "
            f"Preenchidas: {profile.get('valores_preenchidos')} · "
            f"Distintas: {profile.get('valores_distintos')} · "
            f"Min/Max amostra: {profile.get('menor_valor_amostra')} / {profile.get('maior_valor_amostra')}"
        )


def build_agent_context_phase3() -> str:
    base = entry.build_agent_context()
    suggestions = st.session_state.get("relationship_suggestions", [])[:5]
    profiles = st.session_state.get("source_data_profiles", {})
    extra = []
    if suggestions:
        extra.append("\nSugestões automáticas recentes de relacionamento:")
        for item in suggestions:
            extra.append(
                f"- {item.get('left_name')}.{item.get('left_column')} = "
                f"{item.get('right_name')}.{item.get('right_column')} "
                f"score={item.get('score')} confiança={item.get('confidence')}"
            )
    if profiles:
        extra.append("\nPerfis de dados calculados:")
        for profile in profiles.values():
            extra.append(
                f"- {entry.source_name_from_path(profile.get('path', ''))}.{profile.get('column')}: "
                f"linhas={profile.get('total_linhas')}, preenchidas={profile.get('valores_preenchidos')}, "
                f"distintas={profile.get('valores_distintos')}"
            )
    if extra:
        extra.append("\nUse score/perfil como apoio. Não trate sugestão automática como relacionamento confirmado se ela não estiver em Relacionamentos conhecidos.")
    return base + "\n".join(extra)


def render_source_manager_content_phase3():
    phase3_state()
    tab_dremio, tab_planilha, tab_conectadas, tab_relacionamentos, tab_sugestoes, tab_perfil = st.tabs([
        "Dremio",
        "Planilha",
        "Fontes conectadas",
        "Relacionamentos",
        "Sugestões",
        "Perfil de dados",
    ])
    with tab_dremio:
        entry.render_dremio_source_picker()
    with tab_planilha:
        st.caption("Planilhas continuam disponíveis aqui. A multi-view Dremio é o foco desta fase.")
        entry.base_app.setup_spreadsheet_ui()
    with tab_conectadas:
        entry.render_selected_sources()
    with tab_relacionamentos:
        entry.render_relationship_manager()
    with tab_sugestoes:
        render_relationship_suggestions()
    with tab_perfil:
        render_data_profile()


def hydrate_workspace_from_conversation_phase3(conversation_id: str):
    entry.hydrate_workspace_from_conversation(conversation_id)
    store = entry.base_app.memory()
    if not store or str(conversation_id).startswith("local-"):
        return
    conversation = store.get_conversation(conversation_id)
    if not conversation:
        return
    st.session_state.source_data_profiles = conversation.get("data_profiles") or {}
    entry.apply_agent_workspace_context()


entry.render_source_manager_content = render_source_manager_content_phase3
entry.build_agent_context = build_agent_context_phase3
entry.hydrate_workspace_from_conversation = hydrate_workspace_from_conversation_phase3

if __name__ == "__main__":
    entry.base_app.main()
