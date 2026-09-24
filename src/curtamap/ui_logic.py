"""Lógica pura e testável para a interface do CurtaMap.

Concentra regras de filtragem, agregação para ranking de risco, construção de perfis de usinas,
fixtures de recomendação e estatísticas táticas.
"""

from datetime import timedelta
import polars as pl

# Mapeamento amigável para motivos de falta de previsão/causa
REASON_MAP = {
    "historico_insuficiente": "Histórico insuficiente no período de observação (28 dias)",
    "sem_historico": "Sem registros históricos para esta entidade no slot correspondente",
    "fora_da_grade": "Instante de observação fora da grade de 30 minutos",
    "indeterminado": "Causa histórica indeterminada ou ausente",
    "sem_previsao": "Previsão de ocorrência/volume ausente",
}


def format_no_forecast_reason(motivo: str | None) -> str:
    """Retorna uma descrição didática para a ausência de previsão ou causa."""
    if motivo is None:
        return "Previsão normal"
    return REASON_MAP.get(motivo, f"Sem evidência: {motivo}")


def filter_forecasts(
    df: pl.DataFrame,
    fonte: str | None = None,
    subsistema: str | None = None,
    uf: str | None = None,
) -> pl.DataFrame:
    """Filtra o DataFrame de previsões pelas dimensões especificadas."""
    out = df
    if fonte and fonte != "Todas":
        out = out.filter(pl.col("fonte") == fonte)
    if subsistema and subsistema != "Todos" and "subsistema" in out.columns:
        out = out.filter(pl.col("subsistema") == subsistema)
    if uf and uf != "Todas" and "uf" in out.columns:
        out = out.filter(pl.col("uf") == uf)
    return out


def rank_entities_at_risk(forecasts: pl.DataFrame) -> list[dict]:
    """Processa o conjunto de 48 janelas por entidade e ordena pelo nível de risco.

    Retorna uma lista de dicionários com o resumo executivo da entidade.
    """
    if forecasts.is_empty():
        return []

    # Agrupar por entidade
    entities = forecasts.select(["fonte", "id_ons"]).unique().sort(["fonte", "id_ons"])
    ranked = []

    for row in entities.iter_rows(named=True):
        fonte = row["fonte"]
        id_ons = row["id_ons"]
        sub = forecasts.filter((pl.col("fonte") == fonte) & (pl.col("id_ons") == id_ons))

        # Verificar se possui previsão válida
        has_forecast = sub.select(pl.col("p_corte").is_not_null().any()).item()
        motivo_sem_prev = sub.select(pl.col("motivo_sem_previsao")).to_series()[0]

        if not has_forecast:
            ranked.append(
                {
                    "fonte": fonte,
                    "id_ons": id_ons,
                    "tem_previsao": False,
                    "motivo_sem_previsao": motivo_sem_prev,
                    "total_alertas": 0,
                    "energia_em_risco_mwh": 0.0,
                    "primeira_janela_alerta": None,
                    "max_p_corte": None,
                    "causa_predominante": None,
                    "origem_prevista": None,
                }
            )
            continue

        alert_sub = sub.filter(pl.col("alerta") == True)  # noqa: E712
        total_alertas = len(alert_sub)
        energia_em_risco = sub.select(pl.col("energia_esperada_mwh").fill_null(0.0).sum()).item()
        primeira_janela = alert_sub.select(pl.col("tau").min()).item() if total_alertas > 0 else None
        max_p_corte = sub.select(pl.col("p_corte").max()).item()

        # Causa mais frequente / de maior probabilidade média
        causes = (
            sub.filter(pl.col("causa_prevista").is_not_null())
            .group_by("causa_prevista")
            .agg(pl.len().alias("cnt"))
            .sort("cnt", descending=True)
        )
        causa_pred = causes["causa_prevista"][0] if len(causes) > 0 else "ENE"

        origens = (
            sub.filter(pl.col("origem_prevista").is_not_null())
            .group_by("origem_prevista")
            .agg(pl.len().alias("cnt"))
            .sort("cnt", descending=True)
        )
        origem_pred = origens["origem_prevista"][0] if len(origens) > 0 else "SIS"

        ranked.append(
            {
                "fonte": fonte,
                "id_ons": id_ons,
                "tem_previsao": True,
                "motivo_sem_previsao": None,
                "total_alertas": total_alertas,
                "energia_em_risco_mwh": float(energia_em_risco),
                "primeira_janela_alerta": primeira_janela,
                "max_p_corte": float(max_p_corte) if max_p_corte is not None else None,
                "causa_predominante": causa_pred,
                "origem_prevista": origem_pred,
            }
        )

    # Ordenar: usinas com previsão e maior energia em risco primeiro
    ranked.sort(
        key=lambda x: (x["tem_previsao"], x["total_alertas"], x["energia_em_risco_mwh"]),
        reverse=True,
    )
    return ranked


def get_entity_horizon_profile(
    forecasts: pl.DataFrame, fonte: str, id_ons: str
) -> pl.DataFrame:
    """Devolve as 48 janelas ordenadas para a usina especificada."""
    return (
        forecasts.filter((pl.col("fonte") == fonte) & (pl.col("id_ons") == id_ons))
        .sort("horizonte")
    )


def generate_simulated_recommendations(forecasts: pl.DataFrame) -> pl.DataFrame:
    """Gera fixtures de recomendação compatíveis com RECOMMENDATION_SCHEMA.

    Nota: Esta função produz fixtures rotuladas com `tipo_saida = "simulado"` para uso
    na interface enquanto a Etapa 3 não conclui o módulo definitivo de recomendação.
    """
    if forecasts.is_empty():
        # Retorna DataFrame vazio no schema
        from curtamap.contracts import RECOMMENDATION_SCHEMA
        return pl.DataFrame(schema=RECOMMENDATION_SCHEMA)

    entities = forecasts.select(["fonte", "id_ons", "t0"]).unique()
    rows = []

    for row in entities.iter_rows(named=True):
        fonte = row["fonte"]
        id_ons = row["id_ons"]
        t0 = row["t0"]

        sub = forecasts.filter((pl.col("fonte") == fonte) & (pl.col("id_ons") == id_ons))
        has_forecast = sub.select(pl.col("p_corte").is_not_null().any()).item()

        if not has_forecast:
            continue

        energia_risco = float(sub.select(pl.col("energia_esperada_mwh").fill_null(0.0).sum()).item())
        if energia_risco <= 0:
            continue

        inicio = sub.select(pl.col("tau").min()).item()
        fim = sub.select(pl.col("tau").max()).item() + timedelta(minutes=30)

        # Causa predominante
        causes = (
            sub.filter(pl.col("causa_prevista").is_not_null())
            .group_by("causa_prevista")
            .agg(pl.len().alias("cnt"))
            .sort("cnt", descending=True)
        )
        causa_base = causes["causa_prevista"][0] if len(causes) > 0 else "ENE"

        # Ações e multiplicadores por causa
        if causa_base == "ENE":
            acao_cod = "REC_ENE_01"
            acao_desc = "Reprogramar despacho / Acionar armazenamento ou carga flexível regional"
            f_rec = 0.35
            f_brl = 150.0  # R$ / MWh estimado
        elif causa_base == "CNF":
            acao_cod = "REC_CNF_01"
            acao_desc = "Readequar barramento / Ajustar perfil de geração pós-confluência"
            f_rec = 0.20
            f_brl = 180.0
        elif causa_base == "REL":
            acao_cod = "REC_REL_01"
            acao_desc = "Coordenar proteção e tensão local junto ao agente de transmissão"
            f_rec = 0.15
            f_brl = 200.0
        else:  # PAR
            acao_cod = "REC_PAR_01"
            acao_desc = "Reagendar manutenção programada fora da janela de corte"
            f_rec = 0.50
            f_brl = 160.0

        energia_rec = float(energia_risco * f_rec)
        valor_brl = float(energia_rec * f_brl)
        co2_evitado = float(energia_rec * 0.085)  # tCO2 por MWh (estimativa de fator médio)

        rows.append(
            {
                "fonte": fonte,
                "id_ons": id_ons,
                "t0": t0,
                "inicio": inicio,
                "fim": fim,
                "causa_base": causa_base,
                "acao_codigo": acao_cod,
                "acao_descricao": acao_desc,
                "energia_em_risco_mwh": round(energia_risco, 4),
                "energia_recuperavel_mwh": round(energia_rec, 4),
                "valor_estimado_brl": round(valor_brl, 2),
                "co2_evitado_t": round(co2_evitado, 4),
                "premissas_versao": "v1-simulada",
                "tipo_saida": "simulado",
                "modelo_id": "SimulatedFixtureEngine",
            }
        )

    if not rows:
        from curtamap.contracts import RECOMMENDATION_SCHEMA
        return pl.DataFrame(schema=RECOMMENDATION_SCHEMA)

    return pl.DataFrame(rows)


def compute_tactical_history_summary(history_df: pl.DataFrame) -> pl.DataFrame:
    """Agrega o histórico de cortes observados por mês, causa, subsistema e fonte."""
    if history_df.is_empty():
        return pl.DataFrame()

    df = history_df

    # Garantir coluna corte_mwh
    if "corte_mwh" not in df.columns:
        if "energia_mwh" in df.columns:
            df = df.with_columns(pl.col("energia_mwh").fill_null(0.0).alias("corte_mwh"))
        elif "val_referenciageração" in df.columns and "val_geracao" in df.columns:
            df = df.with_columns(
                (
                    (pl.col("val_referenciageração") - pl.col("val_geracao"))
                    .clip(lower_bound=0.0)
                    .fill_null(0.0)
                    * 0.5
                ).alias("corte_mwh")
            )
        else:
            df = df.with_columns(pl.lit(0.0).alias("corte_mwh"))

    # Normalizar causa / razao
    if "razao_limite" not in df.columns:
        if "causa" in df.columns:
            df = df.with_columns(pl.col("causa").fill_null("DESCONHECIDA").alias("razao_limite"))
        elif "cod_razaorestricao" in df.columns:
            df = df.with_columns(
                pl.col("cod_razaorestricao").fill_null("DESCONHECIDA").alias("razao_limite")
            )
        else:
            df = df.with_columns(pl.lit("ENE").alias("razao_limite"))

    # Normalizar subsistema
    if "subsistema" not in df.columns:
        if "id_subsistema" in df.columns:
            df = df.with_columns(pl.col("id_subsistema").alias("subsistema"))
        elif "nom_subsistema" in df.columns:
            df = df.with_columns(pl.col("nom_subsistema").alias("subsistema"))
        else:
            df = df.with_columns(pl.lit("NE").alias("subsistema"))

    # Normalizar uf / estado
    if "uf" not in df.columns:
        if "id_estado" in df.columns:
            df = df.with_columns(pl.col("id_estado").alias("uf"))
        elif "nom_estado" in df.columns:
            df = df.with_columns(pl.col("nom_estado").alias("uf"))

    # Adicionar ano-mês
    df = df.with_columns(pl.col("din_instante").dt.truncate("1mo").alias("mes"))

    group_cols = ["mes", "fonte", "razao_limite", "subsistema"]
    if "uf" in df.columns:
        group_cols.append("uf")

    summary = (
        df.filter(pl.col("corte_mwh") > 0)
        .group_by(group_cols)
        .agg(
            pl.col("corte_mwh").sum().round(2).alias("corte_mwh"),
            pl.col("din_instante").count().alias("intervalos_com_corte"),
        )
        .sort(["mes", "corte_mwh"], descending=[True, True])
    )

    return summary
