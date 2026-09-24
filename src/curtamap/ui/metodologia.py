"""Tela de Metodologia, Rastreabilidade e Limites do CurtaMap."""

import streamlit as st

from curtamap.ui.components import render_baseline_badge


def render_metodologia_page() -> None:
    """Renderiza a página de explicação metodológica e limitações."""
    st.header("📚 Metodologia, Rastreabilidade e Limites do Produto")
    st.caption("Transparência metodológica obrigatória, limitações e protocolo contra vazamento temporal.")

    render_baseline_badge()

    st.markdown(
        """
        ### 🎯 Princípios Fundamentais do CurtaMap

        1. **Não-Vazamento Temporal Estrito (Protocolo *As-Of*):**
           - Toda previsão produzida no instante $t_0$ consome exclusivamente dados que estariam **efetivamente liberados** pelo ONS até aquele momento.
           - O corte de disponibilidade padrão (`nightly_cutoff`) aplica a latência realista observada na divulgação pública do ONS (dados divulgados retroativamente por lote diário).
           - Vento e irradiância verificados são aceitáveis para análises históricas, mas **nunca são usados como previsão meteorológica $D+1$ sem fonte ex-ante de tempo real com timestamp seguro**.

        2. **Validação da Fórmula da Geração Não Realizada (GNR):**
           - A fórmula do volume de curtailment utilizada pelo CurtaMap foi testada e reproduz exatamente **3.127.621 valores oficiais da GNRa publicados pelo ONS**, sem divergências acima de 0,001 MW.
           - Todos os cálculos seguem a especificação formal documentada em `docs/target-definition.md`.

        3. **Revisões Retroativas do ONS:**
           - A auditoria do CurtaMap revelou que o ONS realiza revisões pós-operação em dados passados (alterando valores históricos meses após a ocorrência).
           - Todos os totais e previsões do CurtaMap são explicitamente **provisórios** e representam a melhor evidência disponível ex-ante, não configurando reconciliação comercial ou CCEE.

        ---

        ### 🔬 Arquitetura dos Modelos

        O pipeline do CurtaMap desacopla a previsão em três problemas complementares:
        - **Ocorrência (Classificação Binária):** Estimativa da probabilidade $P(\\text{corte})$ em cada patamar de 30 minutos.
        - **Volume Condicional (Regressão):** Estimativa do volume cortado em MWmed e MWh condicionado à presença do comando.
        - **Classificação de Causa (`REL`, `CNF`, `ENE`, `PAR`) e Origem (`LOC`, `SIS`):** Diagnóstico da motivação dominante do corte.

        ---

        ### ⚠️ Limitações Assumidas e O que o Produto NÃO Afirma

        - **Preditor Provisório (Baseline):** A versão atual expõe o preditor `SameSlotRecentBaseline`. Ele copia o perfil liberado mais recente no mesmo horário para estabelecer o benchmark mínimo a ser superado pelos modelos definitivos da Etapa 2 (ex: LightGBM).
        - **Recomendações Simuladas:** O painel de recomendações exibe fixtures rotuladas como `tipo_saida = "simulado"` com premissas visíveis, servindo como protótipo para o módulo definitivo da Etapa 3.
        - **Não Garantia Financeira:** Estimativas de R$ recuperáveis e emissões de $CO_2$ evitadas são **cenários simulados de sensibilidade**, e não garantias de despacho, ressarcimento ou compensação regulatória.
        """
    )
