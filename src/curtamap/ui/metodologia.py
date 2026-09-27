"""Metodologia e limites: de onde vêm os números e o que eles não podem afirmar."""

import streamlit as st

from curtamap.contracts import CONTRACT_VERSION, RESERVED_TEST_START, TIMEZONE
from curtamap.painel.rotulos import COMPONENT_LABELS, OUTPUT_KIND_LABELS, format_number
from curtamap.ui import contexto, dados


def _age(prov) -> str:
    if prov.evidence_age_days is None:
        return "não informada"
    low, high = prov.evidence_age_days
    text = f"{format_number(low)} a {format_number(high)} dias antes de t0"
    if prov.oldest_evidence:
        text += (
            f" (observações de {prov.oldest_evidence:%d/%m/%Y %H:%M} a "
            f"{prov.newest_evidence:%d/%m/%Y %H:%M})"
        )
    return text


def render() -> None:
    context = contexto.current()
    if context is None:
        return
    prov = context.provenance
    bundle = context.bundle
    start, end = dados.data_range()
    st.title("Metodologia e limites")

    st.subheader("Esta previsão")
    rows = {
        "Tipo de saída": ", ".join(OUTPUT_KIND_LABELS.get(k, k) for k in prov.output_kinds),
        "Modelo": ", ".join(prov.model_ids),
        "Emissão (t0)": f"{prov.t0:%d/%m/%Y %H:%M} · 48 janelas de 30 min",
        "Corte de dados (corte_dados)": f"{prov.data_cutoff:%d/%m/%Y %H:%M} (exclusivo)",
        "Cenário de disponibilidade": ", ".join(prov.scenarios),
        "Gerada em (gerado_em)": f"{prov.generated_at:%d/%m/%Y %H:%M:%S} ({TIMEZONE})",
        "Idade da evidência": _age(prov),
        "Histórico lido": f"{bundle.history_start:%d/%m/%Y} a {bundle.data_cutoff:%d/%m/%Y}",
        "Cobertura do histórico (28 d)": f"mínima {prov.coverage_min:.0%}, "
        f"mediana {prov.coverage_median:.0%} das meias-horas",
        "Usinas · janelas": f"{prov.entities} · {format_number(prov.windows, 0)}",
        "Janelas sem previsão": f"{prov.windows_without_forecast} (mostradas como sem evidência)",
        "Janelas sem causa": str(prov.windows_without_cause),
        "Intervalo de volume p10–p90": f"{prov.interval_share:.0%} das janelas",
        "Contrato": f"versão {CONTRACT_VERSION}",
    }
    if prov.emitted_at:
        rows["Emitida em (emitido_em)"] = f"{prov.emitted_at:%d/%m/%Y %H:%M}"
    st.table({"Campo": list(rows), "Valor": list(rows.values())})

    if prov.components:
        st.markdown("**Proveniência por componente** (quantas janelas vieram de cada fonte)")
        for name, counts in prov.components.items():
            st.markdown(
                f"- {name}: "
                + "; ".join(f"{COMPONENT_LABELS.get(k, k)}: {v}" for k, v in counts.items())
            )

    st.subheader("Dados")
    st.markdown(
        f"""
- **Fonte:** base de constrained-off eólico e fotovoltaico do ONS, snapshot do hackathon
  (`{"`, `".join(dados.SOURCE_FILES.values())}`), de {start:%d/%m/%Y} a {end:%d/%m/%Y %H:%M}.
- **Chave:** `fonte + id_ons`; o mesmo `id_ons` em fontes diferentes é outra usina.
- **Horário:** timestamps como publicados pelo ONS, sem fuso, lidos como {TIMEZONE}.
- **Volume:** GNR analítica, `max(referência − geração, 0)` nas meias-horas com limitação,
  em MWmed; energia = MWmed × 0,5. Estimativa provisória, não ressarcimento nem liquidação.
- **Teste reservado:** nada a partir de {RESERVED_TEST_START:%d/%m/%Y} é lido ou exibido;
  a emissão mais tardia termina suas 24 h antes disso.
- **Disponibilidade:** o preditor só usa dias já liberados em `corte_dados`, no cenário
  informado acima (lote diário após as 19h30 do dia útil seguinte, com feriados).
"""
    )

    st.subheader("O que os números podem e não podem afirmar")
    st.markdown(
        """
- **Ocorrência:** o modelo diário foi comparado com baselines em backtest temporal
  jan–ago/2026 e validado em setembro de 2026 (fora da amostra). O baseline provisório
  só copia o passado recente: suas probabilidades são 0 ou 1, sem calibração.
- **Causa:** hoje é sempre um baseline (participação das causas na usina em 28 dias ou no
  estado em 7 dias). É uma expectativa condicional (“se houver ordem, qual causa?”).
- **Volume:** na eólica, é a média da usina no horário em 28 dias (baseline); o gargalo é
  meteorológico. Vento e irradiância verificados não são usados como previsão D+1.
- **Incerteza:** quando existe, p10–p90 aparece como barra de erro. Sem intervalo, o número
  é pontual e deve ser lido como ordem de grandeza.
- **Explicações** mostram associações do modelo, não causalidade.
- **Recomendações** e impacto (MWh recuperável, R$, CO₂) são cenários sob premissas; até a
  Etapa 3 chegar, a tela mostra só um exemplo simulado e rotulado.
- **Revisões do ONS:** a publicação é revisada em pós-operação; totais são provisórios.
- **Previsão nula** nunca vira zero: aparece como “sem evidência”, com o motivo.
"""
    )
    st.caption(
        "Referências no repositório: docs/target-definition.md, docs/data-contract.md, "
        "docs/reports/nova-abordagem/README.md e docs/implementation-journal.md."
    )
