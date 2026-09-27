# Números de apoio ao pitch: perda avisada e manutenção remarcada

Análise de 27/09/2026. Código: `src/curtamap/previsao/impacto.py`, com testes em
`tests/test_impacto.py`. Os arquivos gerados nesta pasta são
`camada1_cobertura.csv`, `camada3_manutencao.csv` e `manifesto.json`.

```bash
uv run python -m curtamap.previsao.setembro baixar
uv run python -m curtamap.previsao.setembro prever --modelo models/previsao/diario_ocorrencia_v1_2026-08-30.joblib
uv run python -m curtamap.previsao.impacto --modelo models/previsao/diario_ocorrencia_v1_2026-08-30.joblib
```

## Protocolo e reprodução

- **Período:** dias-alvo de 01 a 24/09/2026, o mesmo teste independente do
  `docs/reports/nova-abordagem/README.md` (seção 3).
- **Modelo:** `diario_ocorrencia_v1`, congelado e com paridade exata ao classificador validado
  em setembro. Limiares: 0,3461 na eólica e 0,3212 na solar.
- **Por que as previsões foram regeneradas:** os arquivos de setembro não estavam mais no
  disco. A publicação do ONS foi baixada de novo em 27/09. O `Last-Modified` agora é 26/09, e
  os SHA-256 são novos (ver `manifesto.json`).
- **A reprodução conferiu:**

  | Fonte | AP | Recall | Precisão | Validado antes (AP / recall / precisão) |
  |---|---|---|---|---|
  | Eólica | 0,9215 | 0,94 | 0,82 | 0,921 / 0,94 / 0,82 |
  | Solar | 0,9074 | 0,90 | 0,81 | 0,907 / 0,90 / 0,81 |

- **Nenhuma regra foi ajustada depois de ver setembro.** A regra de escolha do bloco, a
  janela, as frações de parada e os preços foram fixados no código antes da execução. Setembro
  continua sendo o teste e não serve para calibrar.

## Camada 1: quanto da perda chega avisada (medido)

Energia cortada = GNR analítica (`max(referência − geração, 0)` com restrição) × 0,5 h.

| Fonte | Energia cortada (01–24/09) | Fração em meias-horas avisadas | Taxa de alerta | Controle: `historico` com o mesmo nº de alertas |
|---|---|---|---|---|
| Eólica | 2,82 TWh | **97,2%** | 56% das meias-horas (56% das com potencial) | 97,4% |
| Solar | 1,34 TWh | **96,4%** | 33% das meias-horas (64% das com potencial) | 94,8% |

Contexto medido, por usina × dia, em média:

| Fonte | Horas com corte | Horas em alerta | Horas com potencial > 0 | Usina-dias sem nenhum alerta |
|---|---|---|---|---|
| Eólica | 11,7 h | 13,4 h | 23,7 h | 1% |
| Solar | 7,2 h | 8,0 h | 12,4 h | 4% |

**Leitura:**

- **Fato:** quase toda a energia cortada cai nas horas que o aviso marca na véspera.
- **Fato:** o `historico` (frequência da usina no horário em 28 dias), com o mesmo número de
  alertas, cobre praticamente o mesmo: +0,2 pp na eólica e −1,6 pp na solar.
- **Interpretação:** a camada 1 mostra que **a perda é muito previsível**. **Não** mostra uma
  vantagem da IA. O ganho medido do modelo continua sendo o AP (seção 3 do relatório da nova
  abordagem).
- **Fato de contexto forte:** em setembro, a usina solar média ficou cortada em 7,2 das 12,4
  horas com sol. A eólica média ficou cortada em 11,7 horas por dia.
  - **Consequência de produto:** como o aviso dispara em quase todo dia, "vai ter corte
    amanhã?" informa pouco. O valor está em **quais horas** e em **quais horas ficam
    livres**.
- **Não usar:** a fração de usina-dias com corte que tinham algum alerta (99,9% na eólica).
  Com alerta em quase todo dia, ela não mede nada.

## Camada 3: manutenção remarcada para horas de corte (cenário retrospectivo)

### Premissas

Todas são declaradas. Nenhuma foi medida.

- **Oportunidade:** cada usina-dia com a janela completa tem uma intervenção flexível de 2 h,
  a posicionar em qualquer bloco que comece entre 06h e 16h.
  - **Isto não é frequência real de manutenção.** Não somamos as oportunidades para formar
    uma economia anual.
- **A parada tira uma fração `f` da capacidade.** O conjunto de valores foi fixado antes da
  execução: 5%, 10%, 25% e 50%.
- **Perda de cada meia-hora, pontuada depois com o observado:**
  - sem restrição, perde-se `f × geração`;
  - com restrição, perde-se `max(0, geração − (1 − f) × referência)`.
  - **Hipótese operacional da segunda regra:** a ordem do ONS fixa um teto, e a usina só perde
    o que a capacidade restante não alcança. Não sabemos se o teto seria redistribuído.
- **Estratégias.** Todas usam só a informação da emissão das 20h. Empate: o bloco mais cedo.
  - **CurtaMap:** o bloco com a maior probabilidade média de corte.
  - **`historico`:** o bloco com a maior frequência de corte em 28 dias. É a mesma ideia de
    produto, sem o modelo.
  - **Menor potencial:** o bloco com a menor geração de referência média em 28 dias.
  - **Fixo 08h–10h:** referência ilustrativa. **Não** é a prática observada de nenhum
    gerador.
  - **Oráculo:** o melhor bloco em retrospecto. Serve só como teto e não é alcançável.

### Resultado

Perda média da parada, em MWh por intervenção, com a parada de 10%. As outras frações estão
no CSV.

| Fonte | Fixo 08h | Menor potencial | `historico` | **CurtaMap** | Oráculo |
|---|---|---|---|---|---|
| Eólica (3.654) | 3,95 | 4,19 | 1,89 | **1,76** | 0,53 |
| Solar (1.986) | 14,43 | 12,68 | 8,62 | **9,99** | 1,49 |

Redução da perda com o CurtaMap:

| Fonte | f | vs. fixo 08h | vs. menor potencial | vs. `historico` | Melhor / pior (vs. menor potencial) |
|---|---|---|---|---|---|
| Eólica | 5% | −50% | −53% | −5% | 44% / 7% |
| Eólica | 10% | −55% | −58% | −7% | 46% / 8% |
| Eólica | 25% | −55% | −53% | −8% | 53% / 12% |
| Eólica | 50% | −50% | −39% | −9% | 62% / 18% |
| Solar | 5% | −30% | −20% | **+26%** | 78% / 18% |
| Solar | 10% | −31% | −21% | **+16%** | 77% / 19% |
| Solar | 25% | −26% | −12% | **+5%** | 72% / 24% |
| Solar | 50% | −19% | **+17%** | +1% | 60% / 38% |

A mediana da economia é 0 na maior parte das comparações da eólica. Muitos dias empatam,
porque o bloco das 08h também é cortado.

**Leitura:**

- **Interpretação:** remarcar a parada para as horas de corte funciona como prática.
  - Na eólica, a perda cai mais da metade contra as referências ingênuas, em todas as
    frações.
  - Na solar, a queda é de 20–30% nas frações pequenas.
- **Fato:** contra o `historico`, que é a mesma ideia sem modelo, o CurtaMap quase empata na
  eólica (−5% a −9%) e **perde na solar** (+1% a +26%).
  - **O valor desta camada vem do perfil de corte da usina, e não da IA.**
- **Na solar com parada de 50%, o CurtaMap perde para o menor potencial.**
  - **Hipótese:** com paradas grandes, a folga sob o teto deixa de absorver a parada, e passa
    a importar parar quando há pouca geração.
- **A regra de escolha não foi alterada** para corrigir a solar. Isso seria calibrar no
  teste.
- **Sobre o teto do oráculo:** na eólica, com f = 10%, o CurtaMap captura 66% da economia que
  seria possível com informação perfeita (vs. menor potencial). O oráculo usa o futuro e
  **não** é "recuperável até".

### Em dinheiro (ilustração, não resultado)

- 2,4 MWh por intervenção eólica de 2 h a 10% (vs. menor potencial) × um preço **assumido,
  sem fonte**:
  - a R$ 100/MWh, cerca de R$ 240;
  - a R$ 200/MWh, cerca de R$ 490;
  - a R$ 300/MWh, cerca de R$ 730.
- Não conhecemos quantas intervenções flexíveis uma usina faz por ano. Qualquer total anual
  ou nacional seria inventado e **não** foi calculado.

## Limitações

- São só 24 dias, num mês em que o corte foi a regra: 11,7 h por dia na eólica.
- As usinas e os dias são correlacionados. Não houve teste de significância.
- A regra do teto é hipótese. A redistribuição da ordem entre usinas pode mudar o resultado.
- A intervenção real pode ser indivisível, já agendada, depender de equipe, clima e
  autorização, e exigir mais antecedência que D+1.
- Entidades ONS podem ser conjuntos, e não uma única máquina.
