"""Agregações testadas da EDA. Narrativa e gráficos vivem no notebook da Etapa 1."""

from pathlib import Path

from curtamap.audit import connect, literal, records
from curtamap.data_contract import SPECS
from curtamap.targets import target_sql


def aggregate_table(con, dimensions: list[str], where: str = "true") -> list[dict]:
    order = ",".join(str(i + 1) for i in range(len(dimensions)))
    return records(
        con,
        f"""SELECT {",".join(dimensions)}, count(*) AS rows,
        count(*) FILTER(WHERE restricao_registrada) limited,
        count(*) FILTER(WHERE corte_positivo) positive,
        count(*) FILTER(WHERE NOT volume_valido) invalid_volume,
        count(*) FILTER(WHERE razao_desconhecida) unknown_cause,
        sum(energia_mwh) mwh, sum(energia_bruta_mwh) brute_mwh
        FROM t WHERE {where} GROUP BY ALL ORDER BY {order}""",
    )


EPISODES = """WITH positive AS (
    SELECT *,lag(din_instante) OVER(PARTITION BY fonte,id_ons ORDER BY din_instante) prev
    FROM t WHERE corte_positivo), starts AS (
    SELECT *, CASE WHEN din_instante-prev=INTERVAL 30 MINUTE THEN 0 ELSE 1 END new_episode
    FROM positive), numbered AS (
    SELECT *,sum(new_episode) OVER(PARTITION BY fonte,id_ons ORDER BY din_instante) episode
    FROM starts), episodes AS (
    SELECT fonte,id_ons,episode,count(*) slots FROM numbered GROUP BY ALL)"""


def episode_tables(con) -> tuple[list[dict], list[dict]]:
    """Episódios observados de volume positivo; lacunas e inválidos quebram sequência.

    Duração observada não é duração física completa: bordas podem estar censuradas.
    """
    summary = records(
        con,
        EPISODES
        + """
        SELECT fonte,id_ons,count(*) episodes,count(*) FILTER(WHERE slots=1) single_slot_episodes,
        avg(slots) mean_slots,median(slots) median_slots,max(slots) max_slots
        FROM episodes GROUP BY ALL ORDER BY 1,2""",
    )
    persistence = records(
        con,
        """WITH next_values AS (
        SELECT *,lead(din_instante) OVER w next_time,lead(corte_positivo) OVER w next_positive
        FROM t WINDOW w AS(PARTITION BY fonte,id_ons ORDER BY din_instante))
        SELECT fonte,id_ons,count(*) adjacent_known_pairs,
        count(*) FILTER(WHERE corte_positivo) positive_pairs,
        count(*) FILTER(WHERE corte_positivo AND next_positive) positive_followed_positive,
        count(*) FILTER(WHERE next_positive) next_positive_pairs
        FROM next_values WHERE next_time-din_instante=INTERVAL 30 MINUTE
            AND corte_positivo IS NOT NULL AND next_positive IS NOT NULL
        GROUP BY ALL ORDER BY 1,2""",
    )
    return summary, persistence


def episode_durations(con) -> list[dict]:
    """Distribuição de episódios por número de janelas de 30 minutos, por fonte."""
    return records(
        con,
        EPISODES
        + """
        SELECT fonte,slots,count(*) AS episodes FROM episodes GROUP BY ALL ORDER BY 1,2""",
    )


def daily_persistence(con) -> list[dict]:
    """Pares observados t-24h/t, base do baseline "mesmo horário do dia anterior"."""
    return records(
        con,
        """SELECT c.fonte,count(*) AS pairs,
        count(*) FILTER(WHERE p.corte_positivo) AS previous_positive,
        count(*) FILTER(WHERE c.corte_positivo) AS current_positive,
        count(*) FILTER(WHERE p.corte_positivo AND c.corte_positivo) AS both_positive
        FROM t c JOIN t p ON c.fonte=p.fonte AND c.id_ons=p.id_ons
            AND p.din_instante=c.din_instante-INTERVAL 1 DAY
        WHERE c.corte_positivo IS NOT NULL AND p.corte_positivo IS NOT NULL
        GROUP BY ALL ORDER BY 1""",
    )


def concentration(rows: list[dict]) -> list[dict]:
    result = []
    for source in sorted({r["fonte"] for r in rows}):
        members = sorted(
            [r for r in rows if r["fonte"] == source and (r["mwh"] or 0) > 0],
            key=lambda r: (-(r["mwh"] or 0), r["id_ons"]),
        )
        total = sum(r["mwh"] for r in members)
        if not total:
            continue
        for threshold in [0.5, 0.8, 0.9]:
            running = 0
            for n, row in enumerate(members, 1):
                running += row["mwh"]
                if running >= total * threshold:
                    result.append(
                        dict(
                            fonte=source,
                            threshold=threshold,
                            entities=n,
                            positive_entities=len(members),
                            share=running / total,
                        )
                    )
                    break
    return result


def build_tables(raw: Path) -> dict:
    with connect() as con:
        union = " UNION ALL ".join(
            f"SELECT * FROM read_parquet({literal(raw / SPECS[s].filename)})"
            for s in ["eolica", "fotovoltaica"]
        )
        con.execute("CREATE VIEW original AS " + union)
        # Falhar antes da EDA é melhor que multiplicar MWh ou mascarar identidade inválida.
        errors = con.execute("""SELECT count(*)-count(DISTINCT (fonte,id_ons,din_instante))
            + count(*) FILTER(WHERE fonte IS NULL OR id_ons IS NULL OR din_instante IS NULL
                OR fonte NOT IN ('eolica','fotovoltaica')
                OR epoch_ns(din_instante)%1800000000000<>0) FROM original""").fetchone()[0]
        if errors:
            raise ValueError(f"Chaves duplicadas/nulas, fonte ou grade inválida: {errors}")
        con.execute(
            "CREATE VIEW t AS SELECT *,year(din_instante) AS year,"
            "strftime(din_instante,'%Y-%m') AS period," + target_sql() + " FROM original"
        )
        dimensions = {
            "annual": ["fonte", "year"],
            "annual_cause": ["fonte", "year", "causa"],
            "monthly": ["fonte", "period"],
            "monthly_cause": ["fonte", "period", "causa"],
            "state": ["fonte", "year", "id_estado"],
            "subsystem": ["fonte", "year", "id_subsistema"],
            "entity": ["fonte", "id_ons"],
            "entity_month": ["fonte", "id_ons", "period"],
            "hour": ["fonte", "hour(din_instante) AS hour"],
            "season": ["fonte", "year", "month(din_instante) AS month"],
            "label_coverage": ["fonte", "period", "causa", "origem"],
        }
        result = {key: aggregate_table(con, groups) for key, groups in dimensions.items()}
        result["concentration"] = concentration(result["entity"])
        result["entity_metadata"] = records(
            con,
            """SELECT fonte,id_ons,
            string_agg(DISTINCT nom_usina,' / ' ORDER BY nom_usina) AS names,
            string_agg(DISTINCT id_estado,' / ' ORDER BY id_estado) states,
            count(*) AS rows,min(din_instante) AS start,max(din_instante) AS end
            FROM t GROUP BY ALL ORDER BY 1,2""",
        )
        # Critério a priori: 100% das 7344 janelas abr-ago em CADA um de 2024, 2025 e 2026.
        # Painel retrospectivo de sensibilidade; NÃO é seleção de entidades para backtest.
        con.execute("""CREATE TEMP TABLE cohort AS SELECT fonte,id_ons FROM (
            SELECT fonte,id_ons,year,count(DISTINCT din_instante) slots FROM t
            WHERE month(din_instante) BETWEEN 4 AND 8 AND year BETWEEN 2024 AND 2026
            GROUP BY ALL HAVING slots=7344) GROUP BY ALL HAVING count(*)=3""")
        con.execute("""CREATE TEMP TABLE cohort_valid AS SELECT c.fonte,c.id_ons FROM cohort c
            JOIN t USING(fonte,id_ons) WHERE month(din_instante) BETWEEN 4 AND 8
            AND year BETWEEN 2024 AND 2026 GROUP BY ALL HAVING bool_and(volume_valido)""")
        same_window = "month(din_instante) BETWEEN 4 AND 8 AND year BETWEEN 2024 AND 2026"
        result["comparable"] = aggregate_table(con, ["fonte", "year", "causa"], same_window)
        result["fixed_panel"] = aggregate_table(
            con,
            ["fonte", "year", "causa"],
            same_window + " AND (fonte,id_ons) IN (SELECT fonte,id_ons FROM cohort_valid)",
        )
        result["panel_entities"] = records(
            con,
            """SELECT fonte,count(*) entities FROM cohort_valid
            GROUP BY ALL ORDER BY 1""",
        )
        result["episodes"], result["persistence"] = episode_tables(con)
        result["episode_durations"] = episode_durations(con)
        result["daily_persistence"] = daily_persistence(con)
        result["target_quality"] = records(
            con,
            """SELECT fonte,count(*) AS rows,
            count(*) FILTER(WHERE restricao_registrada) limited,
            count(*) FILTER(WHERE corte_positivo) positive,
            count(*) FILTER(WHERE restricao_registrada AND energia_mwh=0) limited_zero,
            count(*) FILTER(WHERE NOT volume_valido) invalid_volume,
            count(*) FILTER(WHERE entrada_negativa) negative_input,
            count(*) FILTER(WHERE entrada_nao_finita) nonfinite_input,
            count(*) FILTER(WHERE entrada_ausente) missing_input_limited,
            count(*) FILTER(WHERE razao_desconhecida) unknown_cause,
            count(*) FILTER(WHERE rotulo_sem_limite) label_without_limit,
            count(*) FILTER(WHERE val_geracaolimitada=0) zero_limit,
            count(*) FILTER(WHERE restricao_registrada AND
                val_geracaoreferencia-val_geracao<0) clipped_negative_difference,
            sum(energia_mwh) mwh,sum(energia_bruta_mwh) brute_mwh,
            sum(energia_bruta_mwh) FILTER(WHERE NOT volume_valido) quarantined_brute_mwh
            FROM t GROUP BY ALL ORDER BY 1""",
        )
        result["exceptions"] = records(
            con,
            """SELECT fonte,id_ons,din_instante,
            val_geracao,val_geracaoreferencia,val_geracaolimitada,
            entrada_negativa,entrada_nao_finita,entrada_ausente,rotulo_sem_limite,
            energia_mwh,energia_bruta_mwh FROM t WHERE entrada_negativa OR entrada_nao_finita
            OR entrada_ausente OR rotulo_sem_limite ORDER BY fonte,id_ons,din_instante LIMIT 100""",
        )
        result["metadata"] = {
            "primary_files": [SPECS[s].filename for s in ["eolica", "fotovoltaica"]],
            "metric": "max(referencia-geracao,0)*0.5 quando limitado e entradas válidas; "
            "zero sem limite; nulo se limitado inválido",
            "panel_rule": "abr-ago de 2024/2025/2026; 7344 janelas/entidade/ano; volume válido",
            "time_zone": "timestamp sem fuso; horários como publicados, sem conversão",
            "status": "estimativa analítica provisória; não representa liquidação CCEE",
        }
        return result
