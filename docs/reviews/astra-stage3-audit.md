# Auditoria adversarial da Etapa 3 — Zelo

Data: 23/09/2026. Entrega auditada: `origin/etapa-3-recomendacao`, commit `ff8461b`.
Branch de trabalho: `auditoria-etapa-3-astra`. Sem merge, push ou alteração de
`app.py`, `contracts.py` e `forecasting.py`.

## 1. Veredito executivo

**A entrega original não sustentava os números do próprio exemplo de recuperação e continha
uma afirmação regulatória excessiva.** As correções permitem demonstrar um backend de cenários
com controles melhores; não tornam a Etapa 3 um produto operacional validado.

O exemplo de 148,14 MWh em risco continua reproduzível. Entretanto, a concentração da energia
em duas das quatro meias-horas limita a carga a 33,112 MWh, a 30 MW. O cenário base correto é
**29,8008 MWh recuperáveis**, contra 54 MWh publicados anteriormente. Valor bruto base:
**R$ 9.246,89**, contra R$ 16.755,66. Nenhum desses valores é recuperação, venda ou pagamento
realizado. A mudança decorre de física por intervalo, não de escolha de modelo.

Também é incorreto transportar o fato “referência final publicada para REL” para a conclusão
jurídica universal “somente REL pode ensejar ESS”. A legislação posterior considera
confiabilidade em contextos e condições próprios. O protótipo continua sem cálculo de compensação.

| Categoria | Conclusão |
|---|---|
| Fatos confirmados | Taxonomia ONS; existência dos números oficiais; reprodução aritmética; comportamento dos testes e do recorte permitido; interface ainda preparatória |
| Defeitos técnicos confirmados | Limite agregado de potência, indeterminação convertida em zero, validação incompleta, mistura de proveniência, falta de barreira na recomendação e testes legados perigosos |
| Interpretações | Margem de operação pode apoiar sensibilidade de deslocamento; não prova qual geração seria substituída |
| Hipóteses de produto | Utilidade das ações, manutenção antecipada, fluxo LOC/SIS, tolerância do operador à antecedência prevista |
| Premissas de cenário | Bateria disponível, potência de carga, energia útil livre, eficiência, preço histórico e fator de emissão deslocada |
| Decisões humanas | Elegibilidade regulatória/contratual, permissão de carga e descarga, conexão, SOC, utilidade operacional e metodologia climática aplicável |

**Condição para apresentação:** mostrar os valores corrigidos como cenários independentes,
usar os avisos da seção 7 e não declarar a validação humana concluída.

## 2. Escopo e evidências consultadas

### Repositório e método

Preparação executada na ordem: `git status --short --branch` (limpo), `git fetch origin`,
comparação com `origin/main`, criação da branch sobre a entrega remota. Commits auditados:
`51e4ed4`, `7ca565f`, `a1feda2`, `ff8461b`.

Leitura integral de `AGENTS.md`, `docs/parallel-plan.md`, `architecture.md`, `roadmap.md`,
`target-definition.md`, `pitch-notes.md`, `recommendation-rules.md`, `configs/premissas/v1.json`,
`src/zelo/{contracts,forecasting,targets,recommendation,app}.py`,
`tests/test_{recommendation,contracts}.py`; leitura das últimas entradas do diário (linhas
505–695 da entrega original). Inspecionados ainda os testes de previsão/notebook e os pontos
de leitura dos módulos legados. Estatísticas antigas nos documentos não foram recalculadas
nem usadas como evidência nova, especialmente as que abrangem o período protegido.

TDD: a primeira bateria adversarial teve **42 falhas / 24 aprovações** no código original.
Após correções e casos adicionais: **241 testes aprovados / 2 ignorados** na suíte completa.
Os dois ignorados abrem outputs ou executam a EDA integral da Etapa 1, incompatível com a
proteção atual. Ruff, formatação e `git diff --check` passaram.

A única leitura real nesta auditoria foi `[26/04/2026 00h, 28/04/2026 00h)` via `load_history`,
com filtro temporal antes de `collect()`. Emissão 29/04/2026 10h. Nenhuma chamada liberou o teste;
nenhuma observação a partir de 01/05/2026 foi selecionada, agregada ou usada como exemplo.
Testes de rejeição utilizam timestamps sentinela, sem dados reais desse período.

### Fontes primárias e acesso

Identificadores abaixo são usados nas tabelas. Todos consultados em 23/09/2026.
O [registro de evidências](stage3-evidence.json) contém URLs, checksums dos downloads disponíveis,
células, entradas da recomputação e medidas do recorte real. Fontes secundárias encontradas na
busca não fundamentam os vereditos.

| ID | Fonte e trecho efetivamente consultado | Resultado de acesso |
|---|---|---|
| O1 | [Dicionário principal eólico ONS](https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_eolica_tm/DicionarioDados_RestricaoContrainedoff_UsiEolicas.json) e [solar](https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_fotovoltaica_tm/DicionarioDados_RestricaoContrainedoff_UsiFotovoltaica.json): razão, origem e referência final | Download direto; hashes iguais aos snapshots de `docs/sources` |
| O2 | [NT-ONS DOP 0022/2025](https://www.ons.org.br/AcervoDigitalDocumentosEPublicacoes/NT-ONS%20DOP%200022.2025%20-%20Crit%C3%A9rios%20para%20Gest%C3%A3o%20de%20Excedentes%20Energ%C3%A9ticos.pdf), §§ 6–7, especialmente pp. 19–22 | PDF integral; trecho regulatório extraído diretamente |
| A1 | [REN ANEEL 1030/2022](https://www2.aneel.gov.br/cedoc/ren20221030.pdf), com alterações da REN 1073/2023 | Acesso direto 403; texto integral não confirmado nesta auditoria; snippet não substitui leitura |
| O3 | [RO-AO.BR.13 Rev.08](https://www.ons.org.br/%2FMPO%2FDocumento%20Normativo%2F4.%20Rotinas%20Operacionais%20-%20SM%205.13%2F4.3.%20Rotinas%20P%C3%B3s-Opera%C3%A7%C3%A3o%2F4.3.2.%20Apura%C3%A7%C3%A3o%20de%20Dados%2FRO-AO.BR.13_Rev.08.pdf) | URL citada respondeu 404; não declarar leitura desse documento |
| L1 | [Lei 15.269/2025](https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/l15269.htm), art. 9, e [Lei 10.848/2004 consolidada](https://www.planalto.gov.br/ccivil_03/_ato2004-2006/2004/lei/l10.848.htm), art. 1 §§ 10–11 e art. 1º-B | Texto legislativo consultado diretamente |
| C1 | [CCEE InfoBandeira 86, junho/2025](https://www.ccee.org.br/documents/80415/30094498/86%20-%20InfoBandeira%20Tarif%C3%A1ria_2025_06.pdf/d2abc6e2-fa3e-43f5-02d4-12bfde14c070), p. 3, tabelas 13, 14 e 17 | PDF acessível pela ferramenta web; download direto 403; checksum indisponível |
| C2 | [CCEE CO 482/26, 18/06/2026](https://www.ccee.org.br/en/web/guest/-/co-ccee-disponibiliza-novas-versoes-de-regras-de-comercializacao-referentes-ao-constrained-off-de-usinas-solares-fotovoltaicas-ren-1.158-2026) | Comunicado integral; confirma novas regras solares e vigências, não substitui os módulos completos |
| C3 | [CCEE CO 971/25, 30/12/2025](https://www.ccee.org.br/-/informacoes-sobre-as-apuracoes-e-reapuracoes-dos-ressarcimentos-associados-a-constrained-off-usinas-eolicas-e-solares-lei-15.269-2025) | Comunicado integral; suspensão então comunicada não foi tratada como situação atual de cada agente |
| M1 | [MCTI, planilha 2025 corrigida](https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/sirene/dados-e-ferramentas/fatores-de-emissao/arquivo/Despacho_2025_jandez_corrigidacomMO.xlsx), aba MDL, C12:N12 | Arquivo original baixado e células numéricas extraídas; SHA-256 no registro |
| M2 | [MCTI, explicação dos fatores](https://www.gov.br/mcti/pt-br/acompanhe-o-mcti/sirene/dados-e-ferramentas/fatores-de-emissao) | HTML integral baixado; distinção inventário/margens e aviso de revisão da base em 2025 |
| B1 | [Portaria Normativa MME 136/2026](https://www.gov.br/mme/pt-br/acesso-a-informacao/legislacao/portarias/2026/portaria-normativa-mme-n-136-2026.pdf), art. 2 §§ 3–7 e art. 7 | PDF integral; p. 4 também renderizada e inspecionada |
| B2 | [PDE 2030 EPE](https://www.epe.gov.br/sites-pt/publicacoes-dados-abertos/publicacoes/PublicacoesArquivos/publicacao-490/PDE%202030_RevisaoPosCP_rv2.pdf), p. impressa 294 / página PDF 300 | PDF integral; página relevante renderizada e inspecionada |
| M3 | [MME, regulamentação do termo de compromisso](https://www.gov.br/mme/pt-br/assuntos/noticias/mme-regulamenta-procedimentos-para-celebracao-de-termo-de-compromisso-sobre-compensacao-por-cortes-de-geracao), 22/07/2026 | Notícia oficial integral; informa Portaria 140/2026 e período histórico. Link do DOU não abriu: anexos não auditados |

A notícia de BESS originalmente citada redirecionou a login. Os requisitos foram conferidos
**na Portaria 136**, não no snippet da notícia. A REN 1158 também teve acesso direto bloqueado;
C2 sustenta apenas as alterações que o próprio comunicado descreve.

## 3. Defeitos confirmados, por severidade

Linhas “original” referem-se ao commit `ff8461b`; linhas “atual” à implementação corrigida.
P1 compromete resultado/proteção ou narrativa central; P2 compromete robustez/rastreabilidade.

| ID / severidade | Evidência técnica e consequência | Tratamento |
|---|---|---|
| D1 / P1 | Original `src/zelo/recommendation.py:155`: `min(total, potência × duração)` permite usar potência ociosa de uma janela em outra. Contraprova 99/1 MWh → carga máxima 16, não 30 MWh | Corrigido em `recommendation.py:152`: perfil de 30 min, passado por `build_recommendations:248`; exemplo real corrigido |
| D2 / P1 | Original `recommendation.py:54` e `:135`: valida só versão; energia negativa pode produzir recuperação negativa; eficiência inválida, NaN, preço/fator negativo e cenários faltantes entram no cálculo | `assumptions.py:11`, `:39`, `:63` e `recommendation.py:161`: rejeição explícita antes de calcular; rejeição de overflow |
| D3 / P1 | Original `recommendation.py:149`: bateria incompleta vira recuperação zero; original `:267`: Polars soma nulos como zero e oculta total parcial | Cenário com valor nulo justificado continua nulo; construção recusa energia indeterminada (`:272`). Resumo preserva total nulo e expõe subtotal/contagens (`:298`) |
| D4 / P1 | Original `recommendation.py:73` aceita previsão externa no período reservado; validação de contrato não barra datas. Original `tests/test_forecasting.py:192` liberava explicitamente o teste; `tests/test_notebook.py:14`/`:27` abria/executava EDA integral | Guardas locais em `recommendation.py:78`; suíte legada isolada antes de executar. Restrição não universal: ver §4 |
| D5 / P1 | Original `recommendation.py:30` afirma exclusividade de REL para ESS. O1/O2 descrevem apuração publicada, mas L1 impede conclusão jurídica universal; CNF não autoriza negar direito | Texto de REL/CNF corrigido; nenhum cálculo financeiro regulatório implementado |
| D6 / P2 | Original `recommendation.py:156` trata 120 MWh como energia de entrada; B1 define compromisso de energia entregável no PMI. O significado do limite estava ambíguo | V2 usa `base_capacidade=saida_util`; v1 arquivada mantém convenção de entrada; capacidades de placa exigem conversão validada |
| D7 / P2 | Original `recommendation.py:108` só verifica tipo/modelo por episódio; corte, cenário e geração da emissão podem divergir sem erro | Validação de metadados por `fonte+id_ons+t0`, antes de filtrar alertas (`:87`). Instantes de observação diferentes são permitidos |
| D8 / P2 | Original `recommendation_rule:177` aceita origem inválida e antecedência negativa; o contrato também admite emissão fora da grade se tau acompanha t0 | Validação local em `:221` e `group_risk_windows:84`; antecedência descrita como diferença de timestamps |
| D9 / P2 | Original `build_recommendations:222` escolhe primeiro cenário se base falta; seleção muda silenciosamente | Exige baixo/base/alto completos; ausência de valor é explícita, não ausência estrutural |
| D10 / P2 | Sem teste automatizado entre leitor, preditor e recomendação; a execução manual não protegia integração | Testes sintético em Parquet temporário e real opcional de dois dias; ambos executados nesta máquina |

**Não é defeito:** causa/origem que mudam ficam nulas no episódio, em vez de eleger uma dominante.
É conservador e testado. Uma lacuna de horizonte quebra episódio; não se preenche a lacuna com zero.
Emissões sobrepostas continuam separadas, assim como o mesmo `id_ons` em fontes diferentes.
A propriedade `0 ≤ recuperável ≤ risco` foi exercitada em 15 combinações de energia/duração,
além de perfis, zero, nulos e entradas inválidas. “Alto” pode ficar abaixo de “base” se a potência
for menor: o código não reordena resultados para fabricar monotonicidade.

## 4. Riscos metodológicos

### Energia, operação e finanças

- **Estado físico ausente:** o cenário assume toda a capacidade útil livre e uma descarga futura
  possível. Não modela SOC, rampas, degradação, auxiliares, potência de descarga, ponto de conexão
  ou comando. Não somar episódios independentes como se fossem uma programação de uma bateria.
- **Energia esperada não é trajetória:** aplicar `min` à expectativa de energia não produz a
  expectativa da energia recuperada. Em um modelo probabilístico, a não linearidade pode
  superestimar a recuperação média. O baseline 0/1 não resolve a incerteza física. Exigir
  trajetórias/amostras ou apresentar apenas cenário condicionado; não chamar de benefício esperado.
- **Escala do ativo:** `id_ons` pode ser conjunto. Uma bateria fictícia por conjunto pode ser
  incompatível com conexão e propriedade reais. 30 MW de saída de leilão não prova 30 MW de carga.
- **Valor:** energia de saída × proxy de PLD é valor bruto ilustrativo. Faltam contrato,
  submercado, hora da descarga, perdas comerciais, tributos, tarifas, CAPEX/OPEX e custo de
  oportunidade. Não mede lucro nem ESS. Preço realizado futuro seria vazamento numa decisão D+1;
  separar previsão de preço disponível em t0 de avaliação econômica posterior.
- **Tempo:** o contrato adota patamares `[tau,tau+30min)` e horário de Brasília; a validação física
  dessa convenção no arquivo ONS continua pendente conforme `target-definition.md`.
  `inicio−t0` é antecedência nominal; não incorpora latência de processamento, reação ou execução.
- **Parcialidade:** `validate_forecast` permite emissões parciais. As funções agregam somente o
  que recebem. Uma emissão vazia ou incompleta não significa “sem risco nas próximas 24 horas”.

### Carbono

M2 distingue fator médio de inventário (toda a geração), margem de operação (despacho marginal)
e margem combinada (operação/construção, segundo metodologia e pesos aplicáveis). A média dos
12 valores de M1 **não é margem combinada, fator médio de inventário nem fator anual ponderado
por energia**. A página do MCTI vincula os fatores MDL à metodologia específica; não certifica
um cálculo de bateria por simples multiplicação.

**Interpretação da auditoria:** para uma sensibilidade operacional de curto prazo, margem de
operação na **hora de descarga** é mais pertinente que fator médio de inventário. Mesmo assim,
precisa existir geração marginal deslocada. Durante excedente, a carga pode não deslocar emissão
alguma; a descarga pode competir com outra renovável. Se houver carga da rede, suas emissões
devem ser descontadas. Bateria, por si só, não cria adicionalidade.

Manter a saída como **“cenário indicativo de emissões potencialmente deslocadas”**. Um cálculo
líquido exige contrafactual validado, trajetória de carga/descarga e emissões adicionais/perdas;
pode ser zero ou negativo. O contrato atual proíbe `co2_evitado_t` negativo
(`contracts.py:275`): não o reutilizar para um indicador líquido sem proposta de contrato.

### Proteção temporal: alcance real das barreiras

| Caminho | Situação verificada por código/teste |
|---|---|
| `load_history`, `forecasting.py:92` | Recusa `end > 01/05/2026` antes de abrir Parquet; `[start,end)` torna `end=01/05` permitido; filtro antes da coleta |
| `SameSlotRecentBaseline.predict`, `:141` | Recusa horizonte que cruza a fronteira, por padrão; filtra dados pelo corte antes de selecionar valores |
| `group_risk_windows` / `build_recommendations` | Agora recusam patamares no período protegido, inclusive fim cruzando a fronteira, e proveniência temporal incompatível |
| `summarize_history` | Recusa timestamp nulo ou pertencente ao período protegido antes de derivar/agregar |
| `impact_sensitivity` / `recommendation_rule` | Não recebem datas nem observações; não podem certificar origem temporal dos escalares. Chamador é responsável |
| `contracts.py:158` / `:251` | Validadores de formato/coerência, sem barreira de período; não tratá-los como leitor autorizado |
| `known_entities`, `derive_targets`, acesso direto a Polars/DuckDB | Transformações genéricas; não constituem barreira de acesso. Não usá-las para abrir dados fora do leitor autorizado |
| `audit.py:65`, `eda.py:119`, `public_reference.py:88` e notebook da Etapa 1 | Leitores legados sem proteção global. Não executados. Requerem trabalho separado de governança se a equipe quiser bloqueio universal |

Portanto, **não foi demonstrado bloqueio em todos os caminhos possíveis do repositório**. A
opção pública de liberação ainda existe no preditor/leitor por desenho anterior; não foi usada.
Removê-la ou centralizar acesso deve ser decisão explícita do responsável, sem interferência
silenciosa na trilha da Etapa 2. A interface deverá usar exclusivamente o caminho protegido.

### Desempenho

Recorte real: 22.176 linhas, 11.088 previsões, 500 recomendações, 597 grupos táticos.
Tempos numa execução: leitura 0,584 s; predição 0,053 s; recomendação 0,116 s; resumo 0,006 s.
Frames: 2.261.328 / 2.618.448 / 293.060 bytes. RSS máximo do processo macOS: 722.534.400 bytes
(~689 MiB); inclui runtime, buffers/decodificação e não só frames. Não é consumo incremental.

O cálculo usa Polars, sem pandas. A iteração Python é por episódio, não sobre a base completa
(`recommendation.py:254`). O leitor filtra e projeta colunas antes de coletar; o resumo recebe
DataFrame já materializado. Esses tempos não demonstram escalabilidade para 100 milhões de
linhas. Na Etapa 4, recortar antes da coleta, cachear por versão/corte e medir concorrência;
para histórico extenso, planejar agregação lazy/streaming. Não houve benchmark integral.

## 5. Auditoria de cada premissa

| Valor original | Veredito | Reprodução e uso admissível |
|---|---|---|
| R$ 58,60/MWh | **Confirmado** | C1 tabela 17: piso 2025; sensibilidade histórica, não previsão de 2026 |
| R$ 310,29/MWh | **Correto com ressalva** | C1 tabelas 13–14: `Σ(horas×PLD)/720 = 310,29297222`, arredonda 310,29; expectativa DECOMP junho/2025 para SE/CO, NE e N, não PLD realizado nem preço Sul |
| R$ 751,73/MWh | **Precisa ser corrigido** na descrição | Número confirmado em C1 tabela 17; **teto estrutural**, não teto horário universal. Descrição corrigida na v2 |
| 0,2146 tCO₂/MWh | **Confirmado** como referência histórica | M1 `MDL!E12`, março, mínimo das 12 células |
| 0,4124666666666667 tCO₂/MWh | **Correto com ressalva** | M1 `MDL!C12:N12`: soma 4,9496 / 12 = 0,4124666666…; diferença final de representação de float irrelevante, não fator anual oficial ponderado |
| 0,5780 tCO₂/MWh | **Confirmado** como referência histórica | M1 `MDL!M12`, novembro, máximo das 12 células |
| 30 MW | **Correto com ressalva** | B1 art. 7 III: mínimo de disponibilidade de potência para habilitação. Aplicá-lo como potência de carga local é hipótese adicional, agora rotulada |
| Quatro horas | **Confirmado** no contexto de leilão | B1 art. 7 IV e art. 2 §3: continuidade/compromisso de disponibilidade; não duração universal de bateria |
| 120 MWh | **Correto com ressalva** | Derivado por Python: 30×4. B1 art. 2 §5 refere energia entregável, consideradas perdas no PMI; não é capacidade nominal DC nem energia de entrada |
| 85% | **Confirmado** como requisito | B1 art. 7 VI: RTE mínima ao PMI. Não é eficiência unilateral nem medição do ativo |
| 90% | **Hipótese aceitável**, valor documental confirmado | B2 p. 294: ciclo de LFP em estudo de geração distribuída, SOC 15–100%. Não comprova RTE de BESS centralizado nem autoriza ignorar SOC |

Valores mensais extraídos de M1: 0,2366; 0,2478; 0,2146; 0,2895; 0,3087; 0,4549;
0,5293; 0,5529; 0,5215; 0,5386; 0,5780; 0,4772 tCO₂/MWh. Apenas 2025 foi usado.
Os três cenários combinam extremos de variáveis distintas: **não são percentis conjuntos,
intervalo de confiança, trajetória de mercado ou previsão de carbono**.

Nenhum dos onze números ficou sem verificação primária. Não foi preciso inventar substituto.
Permanecem **desconhecidos/não preenchidos** os valores reais do ativo, contrato, SOC, fator
marginal da descarga futura e compensação elegível; não inferi-los dos parâmetros de referência.

### Convenção de energia na v2

```text
carga_maxima = soma_por_janela(min(energia_em_risco_da_janela, potencia_carga_MW × 0,5 h))
saida_cenario = min(energia_em_risco_total, carga_maxima × RTE, capacidade_util_saida_MWh)
valor_bruto_cenario = saida_cenario × preco_proxy
emissoes_indicativas_cenario = saida_cenario × fator_proxy
```

Aplica-se RTE uma vez à energia carregada; não novamente à saída. Sem perfil, usa-se
`min(total, potência×duração)` somente como teto agregado, não resultado operacional.
Na v1 histórica, capacidade limitava entrada; a convenção foi preservada apenas para reprodução.
O limite de 120 MWh na v2 pressupõe capacidade **útil livre** de saída: não inserir capacidade
nominal de placa nesse campo sem conversão/validação. A escala é ilustrativa, não dimensionamento.

### Reprodução e deriva

`stage3-evidence.json` registra checksum MCTI
`70b5c353da0198d84c53cc622be78d472c79e512ff6c27246401b44bf27b2edf`, células e entradas da média
ponderada CCEE. Para repetir MCTI sem pandas, baixar a URL M1, verificar SHA-256 e extrair
`xl/worksheets/sheet1.xml` do XLSX com `zipfile`/`ElementTree`: valores de C12 a N12, aplicar
`Decimal`, `min`, `sum/12`, `max`. A média de PLD usa as matrizes de horas/preços de C1 preservadas
no JSON, não os números do arquivo de premissas como entrada da verificação.

Recomendação: snapshots imutáveis em armazenamento de artefatos, hash e data em Git, revisão
humana quando o hash mudar. O checksum identifica bytes, não vigência jurídica. A ausência de
checksum do PDF CCEE está registrada como nulo; o PDF foi lido pela ferramenta web. Não aceitar
uma planilha revisada com valores vermelhos antigos: usar as células corrigidas C12:N12.

## 6. Auditoria de cada causa/ação

| Afirmação ou ação | Veredito | Evidência, ressalva e decisão |
|---|---|---|
| REL = indisponibilidade externa | **Confirmado** | O1/O2. Não significa qualquer falha do próprio gerador |
| REL → preservar evidências | **Hipótese aceitável** | Telemetria, recursos meteorológicos e mensagem são coerentes com apuração O2; utilidade antecipatória exige operador |
| Referência final ONS publicada apenas em REL | **Confirmado** como semântica do campo | O1; não substituir referência analítica universalmente por referência final |
| “Somente REL pode ensejar ESS” | **Precisa ser corrigido** | L1 inclui hipóteses/vedações e compensação histórica por indisponibilidade/confiabilidade. Não concluir elegibilidade a partir do código ONS |
| CNF = requisito de confiabilidade, sem indisponibilidade externa do equipamento | **Confirmado** | O2 §7 distingue as motivações |
| CNF → coordenar operação/manutenção flexível | **Exige validação de operador/regulador** | Manutenção não é resposta obrigatória do ONS; pode exigir programação/autorização e até conflitar com disponibilidade necessária |
| CNF sem expectativa financeira nesta versão | **Correto com ressalva** | O produto não calcula direitos; é incorreto afirmar inexistência jurídica de compensação. Preservar também evidências CNF |
| ENE = impossibilidade de alocar geração na carga | **Confirmado** | O1/O2 e L1. Não confundir automaticamente com restrição física local |
| ENE → avaliar BESS | **Hipótese aceitável** | Condicionada a conexão, ativo, SOC e operação. O cálculo não demonstra que se pode elevar geração mantendo comando de limitação; operador deve confirmar |
| ENE sem compensação presumida | **Correto com ressalva** | L1 art. 1 §11 II veda cobertura de sobreoferta naquele encargo. Não é auditoria de todo contrato/contencioso do agente |
| PAR = restrição indicada no parecer de acesso | **Confirmado** | O1, e não a sigla homônima de planejamento PAR/PEL em O2 |
| PAR → revisar acesso; recuperação imediata não quantificada | **Hipótese aceitável** | Revisão/estudo não equivale a autorização nem solução. O código PAR sozinho não decide direitos contratuais; L1 requer leitura documental |
| Origem LOC/SIS | **Confirmado** para taxonomia; **hipótese aceitável** para fluxo | O1 define local/sistêmica; não define proprietário da causa, controlabilidade ou indenização. Código apenas exibe origem; priorização regional está só na documentação |
| Diferenças eólica/fotovoltaica | **Correto com ressalva** | O2 distingue vento/curva e irradiância/função e métodos de fallback de referência. C2 registra regras solares e vigências próprias. Código troca apenas nome da fonte, não implementa apuração específica |
| Antecedência em horas | **Correto com ressalva** | Diferença exata entre timestamps de previsão, não prazo validado para executar. Usar “início previsto… desde a emissão”, com atualização/latência |
| Causa nula → validar causa | **Hipótese aceitável** | Conservador: não inferir causa de volume/origem. Não há previsão PAR pelo contrato atual; regra PAR é acessível diretamente, não via baseline |

O2 pp. 20–21 descreve referências distintas: eólica usa curva e, quando aplicável, segundo menor
valor de dez períodos; solar usa função e média dos quinto/sexto valores ordenados. Isso reforça
que o mesmo volume analítico não substitui apuração financeira. C2 acrescenta tratamento fracionário
do banco de horas e vigências distintas para solar/eólica; não implementar ESS multiplicando
patamares de 30 minutos por PLD.

M3 informa regulamentação do termo histórico em julho/2026. Não reutilizar C3 de dezembro/2025
como prova de suspensão vigente hoje, nem aplicar o termo histórico automaticamente ao episódio
de abril/2026. A equipe precisa de parecer específico, documentos e módulos CCEE vigentes.

## 7. Lacuna de integração com a interface — handoff da Etapa 4

### O que existe

Backend executável: leitor protegido, baseline provisório, validadores, agrupamento, regras,
cenários e resumo tático. Premissas em arquivos versionados. Existem somente em documentação:
fluxo de trabalho regional LOC/SIS, diferenças detalhadas por fonte, validação com profissionais,
simulação operacional de SOC/descarga e escolha econômica real. Nenhum serviço BESS/ONS é acionado.

`src/zelo/app.py:28` cria três abas, mas `:32`, `:40`, `:48` ainda mostram texto preparatório.
Não chama previsão, recomendação ou resumo; contar Parquet não valida seu conteúdo. Nada disso
foi alterado nesta auditoria. A interface de outra branch não foi auditada.

### Funções e exemplo mínimo

```python
from datetime import datetime, timedelta
import polars as pl
from zelo.config import settings
from zelo.forecasting import load_history, nightly_cutoff, SameSlotRecentBaseline
from zelo.recommendation import (
    build_recommendations,
    group_risk_windows,
    impact_sensitivity,
    load_assumptions,
    summarize_history,
)

t0 = datetime(2026, 4, 29, 10)
cutoff = nightly_cutoff(t0)
# Dois dias bastam para reproduzir este exemplo; produção usa janela definida pelo preditor.
history = load_history(settings.data_dir, cutoff - timedelta(days=2), cutoff)
forecast = SameSlotRecentBaseline().predict(history, t0, cutoff)
assumptions = load_assumptions()  # premissas_v2
recommendations = build_recommendations(forecast, assumptions)
tactical = summarize_history(history, "mes")
episodes = group_risk_windows(forecast)
# Para um episódio ENE selecionado:
ene = episodes.filter(pl.col("causa_base") == "ENE")
if ene.height:
    e = ene.row(0, named=True)
    sensitivity = impact_sensitivity(
        e["energia_em_risco_mwh"],
        e["fim"] - e["inicio"],
        "AVALIAR_ARMAZENAMENTO",
        assumptions,
        energy_profile_mwh=e["energia_por_janela_mwh"],
    )
```

Não omitir o perfil ao desenhar a sensibilidade de uma recomendação: isso reproduziria o teto
agregado antigo. O exemplo usa dois dias para auditoria limitada; cobertura histórica exibida
pelo preditor continua calculada sobre 28 dias e precisa aparecer como tal.

### Schemas e estados

`FORECAST_SCHEMA` em `contracts.py:41` é a entrada. Preservar todas as colunas ao chamar
`build_recommendations`; não agregar/renomear primeiro. Chave: fonte + entidade + emissão + horizonte.
Saída contratual `RECOMMENDATION_SCHEMA` em `contracts.py:78`:

| Campos | Tipo / nulabilidade / significado |
|---|---|
| `fonte`, `id_ons` | String; identidade composta, nunca nome de usina como chave |
| `t0`, `inicio`, `fim` | Datetime(us); intervalo final exclusivo; horário conforme contrato |
| `causa_base` | String ou nulo; nulo significa indeterminada/mista |
| `acao_codigo`, `acao_descricao` | String; exibir aviso integral ou equivalente, não só verbo de ação |
| `energia_em_risco_mwh`, `energia_recuperavel_mwh` | Float64 obrigatórios; segunda é cenário isolado, não recuperação real |
| `valor_estimado_brl`, `co2_evitado_t` | Float64 ou nulo; bruto ilustrativo e emissões indicativas |
| `premissas_versao`, `tipo_saida`, `modelo_id` | String; sempre visíveis/acessíveis na rastreabilidade |

`group_risk_windows` acrescenta `origem_base: String?` e
`energia_por_janela_mwh: List(Float64)`; não são novos campos do contrato compartilhado.
`impact_sensitivity` retorna três linhas com `cenario: String` e os três impactos `Float64?`.
A ordem baixo/base/alto é de apresentação, não garantia de magnitude.

Resumo tático: chaves `fonte`, `id_ons`, `causa`, `uf`, `subsistema` (String, causa/atributos
podem ser nulos), `periodo` (Datetime(us), início da semana/segunda-feira ou mês).
Contagens UInt32: `janelas_observadas`, `janelas_com_corte` (positivas conhecidas),
`janelas_volume_nulo`, `janelas_volume_valido`, `janelas_corte_indeterminado`.
`energia_observada_mwh: Float64?` é total somente se completo;
`energia_conhecida_mwh: Float64?` é subtotal disponível, nulo quando todo volume é desconhecido.
Não chamar as contagens de percentuais de cobertura da grade: janelas ausentes não entram no frame.

### Conteúdo obrigatório por aba

**Operação D+1:** seleção explícita de fonte+entidade+t0; 48 horizontes esperados e quantidade
presente/válida; probabilidade, limiar, alerta, energia esperada, causa/distribuição e motivo da
ausência; origem quando houver; cobertura, instante observado, corte, cenário de disponibilidade,
`gerado_em`, tipo/modelo. Episódio: início/fim, antecedência nominal, energia em risco, regra,
cenário base e sensibilidade completa, versão/fontes/unidades das premissas. Intervalos p10/p90
nulos aparecem “indisponíveis”; probabilidades 0/1 do baseline não viram confiança calibrada.

**Visão tática:** intervalo efetivamente consultado (mês/semana podem estar parciais), fonte,
entidade, UF, subsistema, causa, número de observações/cortes conhecidos/indeterminados,
volumes válidos/nulos, energia conhecida e total completo quando existir. Nunca misturar
observado com previsto. Separar cenário de armazenamento de perda histórica.

**Metodologia e limites:** alvo analítico não financeiro; referência ONS revisável;
baseline ainda sujeito à 2C; disponibilidade hipotética e feriados ausentes; período reservado;
premissas históricas e fontes; capacidade de saída/RTE/perfil; ausência de SOC e despacho;
regulação por período/contrato; carbono sem contrafactual; identidade pode ser conjunto.

### Filtros, ordenação e mensagens

- Selecionar **uma emissão** por visualização operacional; nunca somar emissões sobrepostas.
  Filtrar entidades/fontes preservando a chave; filtrar causa após agrupar para não esconder
  causa mista. Não cortar meias-horas antes de construir episódios sem sinalizar truncamento.
- Lista prioritária: energia em risco decrescente, início crescente, fonte e entidade para
  desempate. Permitir filtro de causa/UF/subsistema com atributos de `known_entities` no corte,
  não com atributos futuros. Mostrar cardinalidade do join; não duplicar recomendações.
- Não somar recuperável/valor/carbono entre episódios como carteira factível sem SOC compartilhado.
  Ordenar cenários baixo/base/alto mantendo resultados reais; explicitar quando curvas cruzam.
- Frame vazio: “Nenhuma recomendação nos dados válidos recebidos”. Se faltam horizontes/energia,
  mostrar “Cobertura insuficiente para concluir ausência de risco”; não exibir zero de risco.
- Premissas inválidas: apresentar erro identificável e reter previsão/ação; não substituir por
  padrão silencioso. Energia recuperável nula impede linha contratual: renderizar estado
  “Cenário de energia indeterminado” por caminho de UI separado, sem inventar recomendação numérica.
- Nulo financeiro/carbono: “Não estimado — premissa ausente”. Total tático nulo:
  “Total indeterminado; subtotal conhecido X MWh em N janelas válidas”.

Textos obrigatórios junto aos números:

> Cenário independente por episódio. Depende de ativo disponível, estado de carga, conexão,
> contrato, comando do ONS e descarga futura viável. Não é garantia de recuperação.

> Valor bruto ilustrativo com proxy histórica; não é receita, lucro, ressarcimento ou liquidação CCEE.

> Emissões potencialmente deslocadas sob hipótese. Não mede redução líquida, causal ou certificada.

> Início previsto em X horas desde a emissão. Não é prazo garantido para executar uma ação.

### Testes de integração necessários na Etapa 4

1. Caminho mínimo acima com API real e filtros por identidade composta; sensibilidade bate com
   a linha base de recomendação e preserva perfil.
2. Datas proibidas são recusadas **antes da leitura**; nenhuma opção de interface libera o teste.
3. Vazio, 47 horizontes, volume nulo, causa mista, origem nula, valor nulo e total tático incompleto
   produzem mensagens distintas e não viram zero.
4. Duas emissões sobrepostas não somam; filtro de causa não transforma episódio misto em ENE;
   duas fontes com o mesmo identificador não se confundem.
5. Baseline 0/1 e ausência de intervalos não são apresentados como confiança comprovada.
6. Avisos/fontes/versão acompanham cartões, gráficos, exportações e números do pitch.
7. Cache inclui período, t0, preditor, premissas e versão dos dados; troca de premissa invalida impacto.

## 8. Decisões que a equipe precisa tomar

1. **Agora:** adotar a correção do exemplo e os textos regulatórios; proibir uso dos números antigos
   sem a indicação de resultado superado. Ações sem recuperação física quantificada continuam com
   zero de cenário, mas isso não significa zero de direito financeiro nem zero de valor da ação.
2. **Proposta separada de contrato, não implementada:** permitir `energia_recuperavel_mwh` nula
   com `motivo_sem_impacto`, expor `cenario`, versão/hash das premissas, cobertura do episódio,
   origem/proveniência e, se futuramente calculadas, emissões líquidas assinadas em outro campo.
   Apresentar exemplos ao responsável e Dev 3 em PR pequeno antes de modificar `contracts.py`.
3. **BESS:** manter referência didática por episódio ou financiar uma simulação de despacho com
   dados reais e restrições compartilhadas. Não vender a primeira como otimização da segunda.
4. **Comercial:** usar preço contratual ou preço horário por submercado e horário de descarga;
   definir disponibilidade em t0, custos e direitos separadamente do cenário energético.
5. **Carbono:** manter proxy exploratória rotulada ou remover o cartão até haver contrafactual.
   Se a equipe exigir impacto causal, a saída correspondente deve ser nula, não a multiplicação atual.
6. **Etapa 2C:** decidir elegibilidade/desempenho/calibração das tarefas, modelo, limiar e avaliação
   fora da amostra; a auditoria não escolhe algoritmo e não libera teste reservado.
7. **Etapa 4:** implementar o handoff; as abas desta branch não consomem backend algum.
8. **Governança de dados:** definir barreira central para leitores legados e retorno controlado
   dos testes da EDA; o bloqueio local não protege contra execução arbitrária de scripts.

## 9. Roteiro de validação humana

Nenhuma entrevista foi feita. Os estados abaixo continuam **pendentes**. Registrar nome/função,
data, versão do código/regra avaliada, resposta literal, documentos e decisão, respeitando sigilo.

| Perfil | Afirmação a confirmar / perguntas literais | Evidência solicitada | Decisão dependente e critério |
|---|---|---|---|
| Operador eólico | Preservar telemetria e coordenar manutenção é útil. “Com este alerta, o que você consegue fazer antes da janela?” “Pode carregar BESS aumentando geração sob esse comando?” “Quem autoriza mudar manutenção?” | Procedimento interno, mensagem SINapse anonimizada, curva/telemetria e fluxo de autorização | Manter REL/CNF como orientação se houver ação autorizada e responsável claro; alterar antecedência conforme tempo real de resposta; remover sugestão de manutenção se incompatível com disponibilidade |
| Operador fotovoltaico | A janela diurna, agregação por conjunto e coleta solarimétrica fazem sentido. “Este id representa quantas usinas e quais conexões?” “Quais medições sustentam a referência?” “A recomendação ainda ajuda perto do fim da irradiância?” | Mapeamento conjunto–usina–ponto de conexão, procedimento solarimétrico e exemplo operacional anterior a maio/2026 | Manter texto específico se útil e rastreável; segmentar entidade/conexão quando necessário; remover recomendação física se a escala não corresponde ao ativo |
| Comercialização/CCEE | Preço e apuração não equivalem a receita. “Qual parcela dessa energia poderia ser liquidada e a que preço?” “Que vigência dos módulos e contrato se aplica?” “Como evitar dupla contagem entre venda e compensação?” | Contrato anonimizado, memória de cálculo CCEE, módulos/versões aplicáveis e componentes de custo | Manter somente valor bruto de cenário enquanto não houver método assinado; alterar proxy por preço aplicável; não publicar receita/ESS calculado sem reconciliação |
| Regulatório | Código REL/CNF/PAR sozinho não determina direito. “Qual regra vale para este agente e data?” “As restrições de acesso e conformidade alteram elegibilidade?” “O termo histórico se aplica a este evento e em quais condições?” | Parecer escrito com artigos, atos vigentes, parecer de acesso, enquadramento/outorga e eventual situação judicial | Aceitar afirmação jurídica apenas delimitada por agente/período e fonte; corrigir redação excessiva; remover conclusão de direito se faltar evidência ou houver controvérsia não resolvida |
| Responsável BESS | Potência/capacidade/RTE têm fronteira de medição correta. “120 MWh são nominais, utilizáveis ou entregues no PMI?” “Qual SOC está disponível, potência de carga e descarga e RTE medida?” “Há descarga factível depois e restrição comum a episódios?” | Datasheet, teste de aceitação/RTE, diagrama unifilar, SOC e limites, requisitos de conexão e despacho | Manter cenário apenas com parâmetros declarados; alterar fórmula/convenção se a medição diferir; retirar número de recuperação operacional se capacidade/conexão/descarga não forem demonstradas |

Não pedir nem usar observações reservadas para essas validações nesta fase. Evidência documental
regulatória publicada após maio não se confunde com dados de geração reservados.

## 10. Correções implementadas

- `cae5878`: isolamento da EDA legada e remoção da liberação explícita no teste do baseline.
- `70fa4bc`: validação de premissas/entradas, perfil semi-horário, capacidade útil v2, nulos,
  proveniência, período, regras e regressões. Contrato compartilhado preservado.
- Documentação desta auditoria: registro numérico/fontes, corrigendas no pitch/regras e diário
  append-only. O commit documental é identificável no histórico da branch.

Arquivos de implementação/teste: `src/zelo/assumptions.py`, `recommendation.py`,
`configs/premissas/v2.json`, `tests/test_recommendation.py`, `test_recommendation_adversarial.py`,
`test_forecasting.py`, `test_notebook.py`. Documentos: este relatório, `stage3-evidence.json`,
`docs/recommendation-rules.md`, `docs/pitch-notes.md`, `docs/implementation-journal.md`.
V1 não foi sobrescrita; app, contratos e preditor permanecem intactos.

O novo validador exige estrutura, três cenários, unidades exatas, textos não vazios, URLs HTTPS
sintaticamente válidas, datas ISO válidas/não futuras, valores finitos não negativos e eficiência
em [0,1]. Não aceita booleanos como números. Nulos exigem `lacuna` textual. Isso não verifica
online a autenticidade da fonte nem prova que a premissa é adequada ao ativo.

## 11. Limitações da própria auditoria

- Sem entrevistas, ensaio físico, documentos privados do agente ou certificação regulatória.
- REN 1030/1073/1158 e RO citada não foram lidas integralmente por falhas de acesso; conclusões
  limitadas às fontes oficiais acessíveis, sem tratar snippet como confirmação.
- O anúncio da Portaria 140 foi lido, não seus anexos. Não foi auditado todo o contencioso ou
  estabelecida a situação atual de liquidação de qualquer agente.
- Um recorte real de dois dias não valida previsão nem impacto fora da amostra. O período
  reservado permaneceu intocado; resultados da Etapa 2C não foram inferidos.
- Não foram validadas as instalações reais, a convenção temporal física do ONS, o contrafactual
  climático ou a execução com bases completas/concorrência de usuários.
- Regras de causa não são mecanismos de comando. Os testes validam software, não segurança de
  uma operação elétrica. A interface de outra trilha não foi executada.
- Fontes são revisáveis: hashes e vigências devem ser reavaliados antes da apresentação e de
  qualquer uso comercial. Valores históricos não passam a ser atuais por estarem versionados.

## 12. Próximos passos priorizados

1. **P0 antes do pitch:** incorporar números corrigidos, retirar exclusividade REL e assegurar
   rótulos de cenário/limitações. Não usar 54 MWh como recuperação do episódio original.
2. **P1 produto:** realizar as cinco validações humanas e registrar decisões; fechar convenções
   de BESS/contratos e escolher se carbono deve permanecer visível.
3. **P1 interface:** implementar e testar o handoff da seção 7, com seleção de emissão, perfil,
   cobertura, indeterminação e rastreabilidade.
4. **P1 contrato/governança:** discutir separadamente nulabilidade/motivos de impacto e a
   barreira central do período protegido; não afrouxar guardas para fazer a demo funcionar.
5. **P1 Etapa 2C:** consumir decisão e evidência fora da amostra; repetir a história com o
   preditor aprovado, mantendo a avaliação de impacto independente da qualidade preditiva.
6. **P2 evolução:** despacho com SOC, preço de descarga e custos, contrafactual climático,
   snapshots imutáveis de fontes e benchmark de carga. Só então discutir retorno econômico
   ou benefício climático líquido quantificados.
