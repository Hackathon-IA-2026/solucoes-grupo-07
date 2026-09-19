# Alvo analítico de curtailment — versão 1

A semântica foi conferida em 19/09/2026 nos dicionários atuais do ONS, preservados em
[`sources/manifest.json`](sources/manifest.json), com URL, data e SHA-256. A fórmula
é a definição atual de GNRa, não uma regra de compensação financeira.

Para **uma linha observada** de 30 minutos:

- `restricao_registrada`: `val_geracaolimitada` não nulo, inclusive zero.
- `volume_mwmed`: máximo entre referência menos geração verificada e zero, quando
  limitado; zero fora da limitação.
- `energia_mwh`: `volume_mwmed × 0,5`.
- `corte_positivo`: volume maior que zero; nulo se o volume for indeterminado.
- `causa` / `origem`: códigos normalizados; `DESCONHECIDA` quando limitados sem código
  reconhecido; nulo fora da limitação. `razao_desconhecida` e `origem_desconhecida` são
  flags explícitas.
- `rotulo_sem_limite`: contradição entre etiqueta preenchida e limite nulo. Texto vazio
  ou só com espaços não conta como etiqueta: a publicação atual do ONS usa `''` onde o
  snapshot usa `NULL` (583.761 linhas solares de mai–dez/2024).

Não preencher janelas ausentes com zero. Não usar referência final universalmente:
é específica de REL e da apuração encaminhada à CCEE. A ocorrência escolhida para o
MVP é o comando de limitação; o indicador de volume positivo fica disponível para
avaliar essa diferença na etapa de baselines. A revisão do Opus sugeriu substituir
obrigatoriamente o evento por volume positivo; decidimos preservar ambos e não
antecipar essa escolha metodológica.

## Exceções explícitas

`derive_targets` é uma transformação pura Polars que preserva todas as linhas e os
campos originais. `target_sql` produz projeção equivalente em DuckDB, com testes de
paridade. Nulos, NaN/infinito e valores negativos nos três campos numéricos necessários,
quando há limitação, deixam volume/energia nulos e flags de qualidade. Fora da limitação,
o alvo é zero conforme a semântica ONS; flags de entrada continuam visíveis.

A variante `energia_bruta_mwh` aplica a fórmula também aos negativos finitos apenas
para sensibilidade. A auditoria mediu 20 gerações negativas sob limitação e um limite
negativo: são **21 volumes eólicos indeterminados**, todos em 2026. Sua soma bruta é
3.732,3295 MWh (3.554,826 MWh dos negativos de geração e 177,5035 MWh do limite).
A exclusão do volume dessas linhas é uma decisão conservadora apoiada na auditoria
e na vedação de negativos nos campos do dicionário, não uma correção dos originais.
Os oito negativos solares ocorrem sem limitação e não alteram o alvo zero.

## Validação pública independente do arquivo tratado

```bash
uv run python -m curtamap.public_reference
uv run pytest tests/test_targets.py tests/test_public_reference.py
```

O comando consulta o catálogo ONS, baixa 64 Parquet mensais dos mesmos períodos em
`data/interim/official/` (ignorado), preserva o cache e gera manifesto/checksums e
[`official-comparison.json`](reports/stage1/official-comparison.json).
Não substitui os cinco Parquet originais. Fonte original e publicação atual continuam
separadas; os dados do ONS podem ser revisados em pós-operação.

A fórmula reproduziu **3.127.621 valores publicados não nulos**, sem divergência maior
que 0,001 MW; diferença máxima 2,274 × 10⁻¹³ MW. Isso valida a fórmula nos casos com
referência, geração e GNRa publicadas. **129.615 intervalos solares limitados de 2024
não têm GNRa publicada**: a soma oficial desse período é incompleta. O código não
calcula delta/percentual entre totais quando qualquer lado tem volume indeterminado.
As diferenças por fonte, ano, causa, UF e subsistema ficam no JSON, com contagens e
nulos; comparação de totais não significa reconciliação individual de revisões.

### Correção de 19/09/2026: todos os anos e revisões linha a linha

A versão anterior deste documento citava apenas as diferenças de 2025 (−0,0160% e
−0,0212%). Essa escolha era incompleta: outros anos têm diferenças maiores. A tabela abaixo
lista todos os pares fonte/ano de `official-comparison.json` (snapshot − GNRa publicada):

| Fonte | Ano | Snapshot (MWh) | Publicação atual (MWh) | Δ % | Comparável |
|---|---|---:|---:|---:|---|
| eólica | 2023 (out–dez) | 1.172.806,9 | 1.175.600,9 | −0,238% | sim |
| eólica | 2024 | 9.466.916,2 | 9.548.059,7 | −0,850% | sim |
| eólica | 2025 | 26.212.729,6 | 26.216.925,4 | −0,016% | sim |
| eólica | 2026 (jan–ago) | 16.035.860,1 | 16.207.487,0 | — | não: 21 volumes locais indeterminados |
| fotovoltaica | 2024 (abr–dez) | 3.245.111,2 | 63.103,1 | — | não: 129.615 GNRa não publicadas |
| fotovoltaica | 2025 | 10.998.020,6 | 11.000.352,0 | −0,021% | sim |
| fotovoltaica | 2026 (jan–ago) | 7.976.193,2 | 8.014.824,3 | −0,482% | sim |

A validação da fórmula (`formula_validation`) usa **somente os arquivos oficiais**:
recalcula a GNRa a partir da referência e da geração publicadas e compara com a GNRa publicada.
Ela valida a definição, não a igualdade entre o snapshot e a publicação. Para medir essa
igualdade, `revision_check` junta os dois lados pela chave `fonte + id_ons + din_instante`:

- 10.806.096 linhas casam. 624 linhas eólicas de nov/2024 aparecem só de um lado porque
  o código mudou de `BA4ECLA` (snapshot) para `CJU_BA4ECLA` (publicação atual).
- 132.290 linhas têm geração, limite ou referência diferentes; 173 têm rótulo diferente.
  `NULL` e `''` são tratados como a mesma ausência.
- 52.310 intervalos mudam de energia. A soma snapshot − publicação recalculada é de
  −298.040 MWh, que é a mesma ordem dos deltas anuais acima.
- **47 de 64 meses** diferem. Os arquivos oficiais têm `Last-Modified` entre 13/02/2025 e
  19/09/2026. Meses de 2023 foram regravados em 14/09/2026.

Conclusão: as diferenças vêm de **revisões pós-operação do ONS**, não da fórmula. Elas são
provisórias, porque o ONS pode revisar de novo. Total local de 2025: **37,21075 TWh**, provisório
e específico desta definição. Esse total não valida automaticamente os 20%, os 4.021 MWmed ou
os valores financeiros citados no pitch; os denominadores e os métodos podem diferir.

## Limitações de documentação e próximos passos

O JSON oficial de detail eólico retornou campos do principal, embora sua URL seja a de
detail. Foi preservado como recebido e não usado como schema do detail. O PDF correspondente
confirma a granularidade individual, mas escreve a unidade de velocidade como `m3/s`:
tratar como inconsistência documental, sem inventar correção confirmada. PDFs consultados:

- [Principal eólico, versão 1.5 de 08/09/2026](https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_tm/DicionarioDados_RestricaoContrainedoff_UsiEolicas.pdf).
- [Detail eólico, versão 1.5 de 08/09/2026](https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_detail_tm/DicionarioDados_RestricaoContrainedoff_UsiEolicas_DetalhamentoPorUsina.pdf).

A semântica do alvo está sustentada por dicionário e comparação numérica. A validação
**dos totais como resultado final de negócio** continua provisória: falta reconciliar
revisões e cobertura. O timestamp não informa fuso nem início/fim do patamar. Não
ajustar energia pela duração em minutos dos campos novos sem definição metodológica:
a fórmula aqui usa potência média do patamar de 30 minutos.
