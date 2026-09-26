"""Totais do topo da tela e resumo em texto, gerados de forma determinística.

O resumo só verbaliza números já calculados pelo ranking e pela proveniência. Uma camada
LLM opcional poderia reescrevê-lo, mas nunca produzir ou alterar números.
"""

from dataclasses import dataclass
from datetime import datetime

import polars as pl

from curtamap.painel.proveniencia import Provenance
from curtamap.painel.ranking import STATUS_ALERT, STATUS_NO_EVIDENCE
from curtamap.painel.rotulos import cause_label, format_mwh, plural


@dataclass(frozen=True)
class Totals:
    entities: int
    at_risk: int
    no_evidence: int
    energy_at_risk_mwh: float
    at_risk_unknown_energy: int
    first_alert: datetime | None


def ranking_totals(ranking: pl.DataFrame) -> Totals:
    """`energy_at_risk_mwh` soma só energias conhecidas; as desconhecidas são contadas."""
    at_risk = ranking.filter(pl.col("status") == STATUS_ALERT)
    return Totals(
        entities=ranking.height,
        at_risk=at_risk.height,
        no_evidence=ranking.filter(pl.col("status") == STATUS_NO_EVIDENCE).height,
        energy_at_risk_mwh=float(at_risk["energia_em_risco_mwh"].sum() or 0.0),
        at_risk_unknown_energy=at_risk["energia_em_risco_mwh"].null_count(),
        first_alert=at_risk["primeira_janela_alerta"].min(),
    )


def operational_summary(ranking: pl.DataFrame, provenance: Provenance) -> str:
    totals = ranking_totals(ranking)
    parts = [
        f"Emissão de {provenance.t0:%d/%m/%Y %H:%M}, com dados liberados até "
        f"{provenance.data_cutoff:%d/%m/%Y %H:%M}."
    ]
    if totals.at_risk:
        risk = (
            f"{totals.at_risk} de {plural(totals.entities, 'usina', 'usinas')} em alerta nas "
            f"próximas 24 h, com {format_mwh(totals.energy_at_risk_mwh)} de energia em risco"
        )
        if totals.at_risk_unknown_energy:
            unknown = plural(totals.at_risk_unknown_energy, "usina", "usinas")
            risk += f" ({unknown} em alerta com volume desconhecido, fora da soma)"
        parts.append(risk + ".")
        top = ranking.filter(pl.col("status") == STATUS_ALERT).row(0, named=True)
        name = top["nom_usina"] or f"{top['fonte']}/{top['id_ons']}"
        uf = f" ({top['id_estado']})" if top["id_estado"] else ""
        energy = (
            format_mwh(top["energia_em_risco_mwh"])
            if top["energia_em_risco_mwh"] is not None
            else "volume desconhecido"
        )
        cause = cause_label(top["causa_provavel"]) if top["causa_provavel"] else None
        cause_text = f"causa provável {cause}" if cause else "causa indeterminada"
        if top["causa_mista"]:
            cause_text += " (há mais de uma causa prevista)"
        if provenance.is_baseline:
            confidence = "probabilidade não calibrada (baseline 0 ou 1)"
        else:
            confidence = f"probabilidade média de {top['confianca']:.0%} nas janelas em alerta"
        parts.append(
            f"Maior risco: {name}{uf}, {energy} a partir de "
            f"{top['primeira_janela_alerta']:%d/%m %H:%M}, {cause_text}, {confidence}."
        )
    else:
        parts.append("Nenhuma usina em alerta nas próximas 24 h.")
    if totals.no_evidence:
        parts.append(
            f"{plural(totals.no_evidence, 'usina sem evidência', 'usinas sem evidência')} "
            "para prever: não entram na soma."
        )
    if provenance.is_baseline:
        parts.append(
            "Previsão do preditor provisório (baseline), que repete o mesmo horário do dia "
            "liberado mais recente."
        )
    parts.append("Os números são estimativas do preditor; não é garantia de corte.")
    return " ".join(parts)
