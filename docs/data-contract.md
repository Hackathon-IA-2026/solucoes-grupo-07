# Contrato do snapshot e auditoria — Etapa 1

## Reprodução

```bash
uv sync --dev
uv run python -m curtamap.audit
# Para CI: gera o relatório e retorna 1 se houver achados ou arquivo ausente.
uv run python -m curtamap.audit --strict
uv run pytest tests/test_audit.py
```

A execução lê os cinco Parquet em `data/raw/` sem modificá-los. Produz
[`audit.json`](reports/stage1/audit.json) e [`audit.md`](reports/stage1/audit.md).
O JSON contém SHA-256, tamanho, schema, versão do DuckDB e data da execução.
A pasta de origem é a mesma registrada em `curtamap.download_data`. Não se infere
a data do download original pelo mtime. A auditoria custa alguns minutos localmente;
usa quatro threads e limite de memória DuckDB de 4 GB (não é limite do RSS do processo).
Comparações de multiconjuntos são particionadas por mês para reduzir spill em disco.

O contrato `src/curtamap/data_contract.py` descreve o **snapshot tratado do hackathon**,
não promete equivalência de schema com futuras publicações do ONS. Colunas ausentes,
extras ou com tipo diferente bloqueiam a análise daquele arquivo; os demais arquivos
continuam sendo auditados. Arquivos ausentes/corrompidos viram estados estruturados.
`--strict` é esperado falhar no snapshot atual: achados reais não são ocultados para
obter um selo verde. Isso difere da suíte de testes, que deve passar.

## Evidências verificadas em 19/09/2026

- Cinco arquivos, **102.739.069 linhas físicas**. Esse total inclui sobreposição entre
  principal, integrada e detail; não representa 102 milhões de amostras independentes.
- Principais: 7.951.920 linhas eólicas (out/2023–ago/2026) e 2.854.800 solares
  (abr/2024–ago/2026). A união tem **10.806.720 observações** e 267 entidades.
- A integrada é exatamente um subconjunto dessa união, comparado em **todas as
  colunas e multiplicidades**: faltam apenas 1.365.552 linhas eólicas de out/2023
  a mar/2024; não há linha adicional nem valor alterado. Ela não deve ser concatenada
  às principais. A EDA usa a união das duas principais para preservar a cobertura.
- Nenhuma chave nula, duplicidade ou lacuna interna nas três bases principais/integrada.
  Os instantes estão alinhados em 30 minutos. Não existem `id_ons` compartilhados
  entre fontes neste snapshot; a chave continua sendo `fonte + id_ons + din_instante`,
  pois ausência de colisões observadas não constitui garantia de unicidade global.
- O detail eólico tem **385 duplicatas excedentes**, 819 saltos e 358.844 janelas
  internas ausentes. O solar tem **56 duplicatas excedentes**, 43 saltos e 2.064
  janelas ausentes. Não há deduplicação ou preenchimento automático.
- Existem renomeações: 18 identidades eólicas e 14 solares nas principais têm mais de
  um nome. O JSON permite separar nomes de alterações de UF, subsistema ou CEG.
  A identidade permanece pelo código composto; nomes não são usados para join.
- A principal contém conjuntos e usinas individuais: eólica 169 + 11; solar 83 + 4.
  O detail contém 1.060 usinas eólicas e 560 solares. **Contar entidades das principais
  como usinas físicas seria incorreto.**
- Nos IDs individuais diretamente comparáveis, geração principal e detail coincidem
  em 562.848 intervalos eólicos e 169.536 solares. O snapshot não contém
  `id_ons_conjuntousina`; não foi validado um mapeamento dos conjuntos por nome.
  Essa checagem parcial não autoriza somar ou ratear os dois níveis.

## Qualidade e interpretação

As principais têm 21 gerações eólicas negativas, oito solares negativas e um limite
eólico negativo. Não há NaN/infinito nas colunas numéricas auditadas. A disponibilidade
eólica chega a **3.628.932,699 MWmed**, extremo que exige investigação antes de virar
feature. No detail há vento de **8,0287 × 10²⁶**, irradiância de **123.312,404** e
valores negativos. Esses valores não são evidência meteorológica utilizável D+1.
O contrato não inventa um limite físico com base num percentil: registra contagens,
mínimos, máximos e quantis aproximados para investigação, sem winsorização silenciosa.

Nulos em limite significam ausência de limitação, conforme dicionário. Referência
final é específica de REL, portanto sua ausência nas demais causas é estrutural.
A eólica tem causa/origem em todos os 2.556.832 intervalos limitados; a solar tem
42 rótulos ausentes em 700.331 intervalos limitados. Não há causa preenchida sem
limite nem referência final preenchida fora de REL. O detalhe não tem limite:
cobertura condicionada à limitação é **não aplicável**, nunca estimada por proxy.

`nulls_by_month` inclui denominadores de linhas e intervalos limitados, contagens por
campo e fonte/mês; `coverage` cobre entidade, UF, subsistema e período. Comparações
usam igualdade exata entre snapshots; o check de geração individual usa 0,001 MW.
Lacunas são contadas somente entre o primeiro e o último instante observado por
entidade. Entrada/saída de cadastro não é tratada como falha. Timestamp não tem fuso;
o significado início/fim do patamar não foi confirmado. Não há horário de verão
brasileiro no período 2023–2026, mas isso não resolve a ausência de metadado temporal.

## Decisões e limites para a etapa seguinte

Usar as principais como fonte do alvo; manter detail separado até resolver chave,
duplicidades, outliers e validade da meteorologia histórica. Não usar `ano`, `mes`,
`hora` etc. sem conferir contra `din_instante` (divergências estão no JSON). Nem os
Parquet nem grandes derivados entram no Git. Somente relatórios pequenos e artefatos
resumidos da EDA são versionados.
