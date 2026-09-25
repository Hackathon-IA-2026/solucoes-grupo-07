# Etapa 2C — análise crítica e decisão metodológica

Data: 24/09/2026. Branch `etapa-2-experimental`, sem merge e sem push. Prompt:
`docs/handoffs/stage2c-prompt.md`. Evidências calculadas: `matriz-2c.json` e
`auditoria-baselines-2c.json` (nesta pasta), gerados por `scripts/stage2c/` no commit
`ef95dda`.

**Decisão em uma frase.** Nenhum candidato aprendido é aprovado. As oito células (duas fontes ×
quatro tarefas) ficam em `requer_2d`, porque os modelos da 2B não implementaram a lista de
features aprovada no §8: usaram 12 das cerca de 50 colunas geradas, sem posição do dia, sem
defasagens de mesmo horário e, na causa, sem nenhum histórico de causa. Nesse estado, o
resultado não testa a hipótese do protocolo. Nenhuma receita foi congelada, e o **teste
reservado continua bloqueado**. O melhor baseline de cada célula fica registrado como piso de
comparação da 2D e como saída de demonstração, com a limitação explícita de que ainda não
passou pelo teste.

## 1. O que foi conferido antes de qualquer leitura de desempenho

| Verificação | Resultado | Evidência |
|---|---|---|
| Hashes do handoff | 6/6 OK; SHA-256 do CSV `-002` = `csv_sha256` do resumo (`99920bab…`) | `sha256sum -c SHA256SUMS-handoff.txt` |
| Hashes das runs | 650 entradas de `checksums.json` (16 runs e piloto) recalculadas, **zero divergências** | `scripts/stage2b/conferir_migracao.py`, 149 s |
| Status e falhas | 16/16 `complete`, `failures=[]` | manifestos e relatórios |
| Commit do código | V1 eólica `560ae70`; demais 15 runs `88634ed` | `manifest.code_commit` |
| Configuração, dados e calendário | `configuration_sha256 1ed84727…`, dados `487050da…`/`e2935941…`, calendário `8c3f500b…`, idênticos nas 16 | manifestos |
| Semente | `[42]` nas 16 | manifestos |
| Cortes | V1–V4 conforme o §6.1; tuning e calibração nas fronteiras `C−56`/`C−28` | `reports/*.json → boundaries` |
| Congelamento +24h | Cada joblib contém modelo, pré-processador, calibrador e limiar; os SHA-256 dos 8 modelos de cada sensibilidade são iguais aos da principal (auditoria 2B); sem `fit_seconds` nem pasta `models/` | joblibs inspecionados; `auditoria-runs-2b-001.json` |
| Convergência linear | Todos os `n_iter_` entre 32 e 209, abaixo de `max_iter=1000` | joblibs |
| Classes de causa | Nenhuma classe ausente no treino (`missing_classes=()` nos 16 modelos de causa) | joblibs |
| Vazamento nos baselines | **Zero** linhas com `source_time + 30 min > t0` nas 32 combinações fonte×rodada×baseline; `source_time` nunca nulo | `auditoria-baselines-2c.json`, DuckDB em 37 s |

Nenhuma divergência interrompeu a análise.

## 2. Achados de conformidade (código × protocolo aprovado)

Os achados vêm da leitura do código e dos artefatos. Não são interpretações de desempenho.

### 2.1 Lista de features não implementada (decisivo)

- **Fato.** Os modelos usam `NUMERIC_FEATURES = horizon, history_age_hours,
  history_coverage_28d, positive_frequency_7d, positive_frequency_28d, mean_volume_28d,
  tau_weekday, tau_month` e `CATEGORICAL_FEATURES = id_ons, id_estado, id_subsistema,
  ceg_level` (`src/curtamap/experimental/runner.py`). A lista é idêntica em `560ae70` e em
  `88634ed` e está gravada no pré-processador dos 64 joblibs. Ela veio do commit `8129e6d`
  (22/09), no Mac, sem justificativa no commit nem no diário.
- **Fato.** O dataset de features já contém as demais colunas do §8: posição da meia hora em
  seno e cosseno para `t0` e `tau`, `last_*`, `same_hour_{1,2,3,7}d_*`, `history_*`,
  frequências e volumes em 24h/7d, `cause_*_share_28d`, agregados por UF e subsistema,
  episódio, `hours_since_*`, etc. Os modelos simplesmente não as recebem.
- **Fato.** O `HANDOFF-sessao-01` (§5) registrou "Modelos usam 8 numéricas + 4 categóricas das
  ~50 features geradas" como observação de conformidade "não corrigida; para a 2C". Não existe
  aprovação da lista reduzida no protocolo, no diário nem nos handoffs.
- **Consequências observáveis:**
  - nenhum modelo recebe a posição do dia; na solar, a hora só pode ser reconstruída por
    interação entre `history_age_hours` e `horizon`;
  - nenhum modelo vê o comportamento da entidade no mesmo horário;
  - o modelo de causa não vê última causa nem composição recente de causas.
- **Interpretação (hipótese, não verificada).** A falta dessas informações é a explicação mais
  provável para o LightGBM solar superar tanto a logística e para o recall de REL ficar perto
  de zero.
- **Decisão.** O resultado negativo dos modelos **não** vale como resultado negativo da
  hipótese do §8/§9. A lacuna era conhecível antes de qualquer métrica. Corrigi-la é
  conformidade ao protocolo aprovado, não resgate, mas precisa ser registrada como tal, porque
  V1–V4 já foram vistas.

### 2.2 Baselines de causa fora do §7.2

- **Fato:** em `baselines.py`, `_direct_values` atribui a **última causa reconhecida da
  entidade** (`_entity_last_cause`) a `ultimo_valor`, `mesmo_horario_dia_anterior` e
  `mesmo_horario_recente` sempre que a linha direta existe. Pelo §7.2:
  - `mesmo_horario_dia_anterior` deveria usar a causa em `tau − 24h`;
  - `mesmo_horario_recente` deveria usar a última ordem reconhecida naquele horário.
- **Isso explica o achado da 2B:** `ultimo_valor` e `mesmo_horario_recente` produzem causas
  idênticas nas 8 runs, porque ambos encontram a linha direta em mais de 99,8% das requisições.
- **Desvio menor em `ultimo_valor`:** quando a linha existe, mas não há causa reconhecida em 28
  dias, ele devolve `CNF` em vez da majoritária do fallback.
- **Decisão:** os dois baselines de mesmo horário ficam reportados, mas **fora da escolha do
  comparador de causa**. `ultimo_valor` segue elegível, com o desvio anotado. Com os quatro
  admitidos, o comparador eólico mudaria de `historico` (0,5298) para
  `mesmo_horario_dia_anterior` (0,5309); a solar não muda. O veredito dos modelos é o mesmo
  nos dois casos.

### 2.3 Outros desvios, com efeito limitado sobre esta decisão

1. **Limiar dos baselines de ocorrência.** É fixo em 0,5, sem o procedimento interno do §7.2,
   e o código usa `threshold or 0.5`. Isso afeta precisão, recall e F2, que **não entram no
   §11**. AP e Brier não dependem do limiar. Os limiares dos modelos ficam entre 0,089 e
   0,271, então o `or 0.5` não disparou.
2. **LightGBM com one-hot esparso** das categorias, em vez das categorias nativas do §9.1. A
   parte numérica também é guardada como CSR.
3. **Volume LightGBM** com objetivo Gamma e *early stopping* por L1:
   - na solar V3/V4 isso escolheu `n_estimators=1`, com MAE interno de 69,7 contra 69,2 da
     outra configuração, ou seja, um regressor praticamente constante;
   - não é falha de execução: é o descasamento entre média condicional e erro absoluto,
     previsto no §5.2.
4. **Gamma linear solar** convergiu (61 e 122 iterações), mas extrapola:
   - na V1, MAE condicional de validação de 11.527 MWmed;
   - no tuning da V2, a configuração `alpha=0,01` teve MAE de 20.841.
   - As previsões são finitas e não negativas, logo não são "inválidas" no sentido do §5.2,
     mas tornam `volume-*-linear` sem uso prático.
5. **Elegibilidade e idade:**
   - `history_eligibility` usa `t0`, e não `c(t0)`;
   - nos baselines, os recortes `idade:*` usam a idade do dado do próprio comparador. Assim,
     os recortes de idade de modelo e baseline não cobrem a mesma população.
6. **Sensibilidade +24h incompleta:** sem baselines, sem seis recortes e sem diagnósticos de
   volume. Métricas nulas saem sem motivo gravado.
7. **Processo:**
   - commits de código na máquina dedicada, desvio do §13.3 já registrado na 2B;
   - esta 2C também foi executada no computador Windows, depois da unificação da raiz pedida
     pelo responsável, e não no Mac. É outro desvio de processo, que não altera artefatos.

## 3. Resultados V1–V4 (recorte global, cenário principal)

- **Métricas primárias:** AP (integral em degraus), MAE total em MWmed e macro-F1 das três
  causas.
- **Colunas "Dif." (ocorrência e causa):** diferença absoluta candidato − comparador por rodada.
- **Colunas "Dif." (volume):** redução relativa do MAE; valor negativo é piora.
- **Desvio:** amostral, com n = 4.

### 3.1 Comparadores únicos

Regra: melhor média V1–V4 da métrica primária, com uma única regra para as quatro rodadas.

| Fonte | Tarefa | Comparador | Média | Desvio | Mín–máx | Observação |
|---|---|---|---|---|---|---|
| Eólica | corte_positivo | `historico` | 0,6896 | 0,2163 | 0,3848–0,8865 | `mesmo_horario_dia_anterior` 0,6860 |
| Eólica | restricao_registrada | `historico` | 0,7305 | 0,2197 | 0,4197–0,9232 | idem, 0,7278 |
| Eólica | volume | `mesmo_horario_dia_anterior` | 15,863 | 3,256 | 13,00–20,09 | `historico` 15,872; WAPE médio 1,0032 |
| Eólica | causa | `historico` | 0,5298 | 0,0327 | 0,5012–0,5766 | §2.2 |
| Solar | corte_positivo | `historico` | 0,7063 | 0,1952 | 0,4289–0,8506 | empate com `mesmo_horario_dia_anterior` na 4ª casa |
| Solar | restricao_registrada | `historico` | 0,7699 | 0,2062 | 0,4688–0,9120 | idem |
| Solar | volume | `mesmo_horario_dia_anterior` | 15,063 | 1,063 | 13,59–16,09 | `historico` idêntico até 10⁻³; WAPE 0,9016 |
| Solar | causa | `ultimo_valor` | 0,4786 | 0,0530 | 0,4011–0,5199 | desvio menor do §2.2 |

**Fato (auditoria).** `mesmo_horario_dia_anterior` só encontra o valor nativo em 1,24%–1,33%
das linhas. Em 98,3%–98,5% dos casos ele recai na frequência histórica **entidade × mesmo
horário** dos últimos 28 dias, que é o próprio `historico` (esse nível responde por 99,6%–99,8%
das linhas do `historico`).

- **Interpretação.** Sob a liberação noturna em dia útil, `tau − 24h` quase nunca está
  disponível em `t0`. Os dois baselines vencedores são, na prática, **a mesma regra**: a
  frequência (ou a média) recente da própria entidade naquele horário.
- **Solar, `ultimo_valor` de ocorrência e volume:** prevê sempre zero (AP igual à prevalência,
  WAPE exatamente 1), porque o último dado liberado é noturno.

### 3.2 Candidatos contra o comparador

| Fonte | Tarefa | Candidato | Média | Dif. V1 | Dif. V2 | Dif. V3 | Dif. V4 | Rodadas melhores | Brier ou WAPE médio (cand. / comp.) |
|---|---|---|---|---|---|---|---|---|---|
| Eólica | corte | linear | 0,5056 | +0,0033 | −0,2140 | −0,2150 | −0,3103 | 1/4 | Brier 0,1971 / 0,1361 |
| Eólica | corte | lightgbm | 0,5250 | −0,0505 | −0,2067 | −0,0791 | −0,3220 | 0/4 | 0,1905 / 0,1361 |
| Eólica | restrição | linear | 0,5570 | +0,0018 | −0,1927 | −0,1893 | −0,3137 | 1/4 | 0,2104 / 0,1385 |
| Eólica | restrição | lightgbm | 0,5818 | −0,0243 | −0,1214 | −0,1295 | −0,3197 | 0/4 | 0,2007 / 0,1385 |
| Eólica | volume | linear-linear | 22,271 | −18,8% | −36,0% | −59,5% | −39,2% | 0/4 | WAPE 1,357 / 1,003 |
| Eólica | volume | linear-lightgbm | 20,584 | +1,2% | −30,9% | −52,4% | −25,7% | 1/4 | 1,230 / 1,003 |
| Eólica | volume | lightgbm-linear | 21,299 | −40,3% | −34,1% | −27,3% | −39,0% | 0/4 | 1,367 / 1,003 |
| Eólica | volume | lightgbm-lightgbm | 19,623 | −13,1% | −29,9% | −24,8% | −25,2% | 0/4 | 1,225 / 1,003 |
| Eólica | causa | linear | 0,4110 | −0,1928 | −0,1606 | −0,0878 | −0,0340 | 0/4 | — |
| Eólica | causa | lightgbm | 0,4041 | −0,1644 | −0,1697 | −0,1036 | −0,0650 | 0/4 | — |
| Solar | corte | linear | 0,2919 | −0,2217 | −0,5032 | −0,4993 | −0,4335 | 0/4 | Brier 0,1608 / 0,0827 |
| Solar | corte | lightgbm | 0,6433 | +0,0134 | −0,1591 | −0,0714 | −0,0349 | 1/4 | 0,1130 / 0,0827 |
| Solar | restrição | linear | 0,3323 | −0,2309 | −0,5295 | −0,5113 | −0,4784 | 0/4 | 0,1905 / 0,0827 |
| Solar | restrição | lightgbm | 0,7334 | +0,0639 | −0,0976 | −0,0553 | −0,0570 | 1/4 | 0,1201 / 0,0827 |
| Solar | volume | linear-linear | 236,29 | −5.456% | −107% | −104% | −70% | 0/4 | WAPE 17,67 / 0,90 |
| Solar | volume | linear-lightgbm | 27,263 | −38,0% | −100,4% | −112,0% | −71,5% | 0/4 | 1,572 / 0,902 |
| Solar | volume | lightgbm-linear | 302,91 | −7.362% | −74,0% | −16,8% | −5,0% | 0/4 | 22,95 / 0,90 |
| Solar | volume | lightgbm-lightgbm | 20,406 | −17,9% | −68,9% | −41,2% | −11,4% | 0/4 | 1,179 / 0,902 |
| Solar | causa | linear | 0,4126 | −0,1091 | +0,0003 | −0,0727 | −0,0829 | 1/4 | — |
| Solar | causa | lightgbm | 0,3212 | −0,1717 | −0,0660 | −0,2213 | −0,1708 | 0/4 | — |

**Critérios do §11:** 20 de 20 candidatos falham a margem média e têm menos de três rodadas
melhores. Todos disparam a proteção de piora em alguma rodada; os de ocorrência disparam também
a de Brier, e os de volume, a de WAPE. O módulo `decision.assess_candidate` devolve
`requer_analise` para todos. Nenhum chega perto: o menor déficit médio é o do LightGBM solar de
restrição (−0,0365 de AP), e ele ainda piora mais de 0,02 em três rodadas.

**Diagnósticos de volume condicional** (regressor avaliado sozinho em todas as linhas, fora do
§11): MAE total médio de 41,0 (linear) e 35,3 (LightGBM) na eólica; de 1.227,6 e 73,1 na solar.

### 3.3 Onde o déficit aparece

Média V1–V4 do melhor candidato de cada célula contra o comparador. Detalhe por rodada em
`matriz-2c.json → comparator_slices` e `candidates.*.slices`.

- **Horizonte:** o déficit é praticamente uniforme nas faixas 0–6h, 6–12h e 12–24h. Exemplos:
  - eólica corte: 0,691/0,690/0,688 contra 0,530/0,525/0,522;
  - solar volume: 15,04/15,06/15,08 contra 20,66/20,75/20,11.
- **Interpretação (hipótese):** com a liberação noturna, a informação mais nova já tem um dia
  ou mais em qualquer horizonte. Por isso o horizonte pesa pouco, e a perda vem da
  representação, não de um horizonte específico.
- **Painel fixo e fins de semana/feriados:** o mesmo padrão do global. O prejuízo não está
  concentrado em um recorte; é estrutural.
- **Histórico insuficiente:** métricas idênticas às do comparador, porque ali a previsão
  publicada é o fallback `historico` (fato do código `_with_prediction`). Esse recorte não
  discrimina modelos.
- **Cauda (p99 do treino):** AP nulo na ocorrência (recorte de classe única, conforme o
  §10.1). No volume, o erro na cauda é maior no candidato (eólica 349 contra 283; solar 592
  contra 400).
- **Recortes de idade:** não são comparáveis entre modelo e baseline (§2.3, item 5).
- **Causa, REL:** recall entre 0,000 e 0,300 nos modelos, contra 0,023–0,458 no comparador
  eólico (`historico`) e 0,152–0,524 no solar (`ultimo_valor`). O `ultimo_valor` eólico chega
  a 0,671 na V1. Na eólica V3, a matriz de confusão linear não prevê REL
  nenhuma vez (395.196 casos reais).

### 3.4 Calibração, prevalência e +24h

- **Deslocamento de prevalência (fato).** O refit e a calibração têm prevalências muito
  diferentes. `corte_positivo`, refit → calibração:
  - eólica V3: 0,189 → 0,475; eólica V4: 0,240 → 0,372;
  - solar V3: 0,145 → 0,311.
- **Confiabilidade (fato):** as faixas de confiabilidade da eólica V3 mostram probabilidade
  média abaixo da frequência observada em todas as faixas baixas.
- **Brier:** 0,11–0,21 nos modelos contra 0,08–0,14 nos comparadores.
- **Interpretação (hipótese):** o sigmoide ajustado em quatro semanas não compensa um modelo
  sem sinal recente por horário.
- **+24h, só modelos (a 2B não calculou baselines nesse cenário).** Degradação média do
  primário, com leitura de populações "conhecidas" e não da interseção (§5):
  - eólica: corte LightGBM 0,5250 → 0,5103; volume lgbm-lgbm 19,62 → 19,97 (+1,8%);
  - solar: corte LightGBM 0,6433 → 0,5432; restrição LightGBM 0,7334 → 0,6486; volume
    lgbm-lgbm 20,41 → 22,29 (+9%);
  - a causa linear eólica **melhora** no +24h (0,4110 → 0,4271).
- **Interpretação (hipótese):** isso é coerente com modelos que usam pouca informação recente.
  Não mede a sensibilidade da abordagem aprovada.

### 3.5 Custo e reprodução

- **Principais:**
  - eólica: 4.072–5.067 s por rodada, com a V1 em 13.835 s por usar código de métricas
    anterior;
  - solar: 1.840–4.340 s;
  - total de cerca de 10,9 h.
- **Sensibilidades:** cerca de 2,3 h no total.
- **Pico de processo:** 24,06 GiB (solar V4) e 22,02 GiB (eólica V4). Ambos acima da meta de 20
  GiB da projeção, e o da solar também acima da referência de 22 GiB do §12.1. Isso ocorreu
  **com só 12 features**.
- **Reprodução:**
  - a V1 eólica difere das demais só no código de métricas, com paridade testada;
  - o LightGBM em 6 threads determinísticas é repetível só com o mesmo número de threads;
  - as sementes 17 e 101 não foram executadas.
- **Consequência para a 2D:** a correção da lista de features multiplica as colunas numéricas
  por cerca de 5. A memória precisa ser reprojetada antes de qualquer treino (§4 do prompt 2D).

## 4. Agregações do §10.2 e do §10.3 não calculadas nesta etapa

| Agregação | Estado | Motivo |
|---|---|---|
| Incerteza semanal (bootstrap de blocos de 7 dias) | Ausente | Só pode bloquear uma aprovação. Nenhum candidato passa a margem média, então ela não muda nenhum estado. Obrigatória na 2D. |
| Visão por entidade com peso igual (WAPE agregado e média de WAPEs) | Ausente | Idem: é diagnóstico de concentração. Obrigatória na 2D. |
| Energia diária pela emissão das 00h | Ausente | Idem. Obrigatória na 2D. |
| Interseção principal × +24h | Ausente | O +24h perde de 0,000% a 0,095% das linhas de validação (eólica V1: 42.851.184 contra 42.846.576). A 2B não tem baselines no +24h. Obrigatória na 2D. |
| Incoerência `P(corte) > P(restrição)` | Ausente | Não reportada pela 2B. Obrigatória na 2D. |
| Recall de início de episódio e persistência | Parcial | Existe só nas runs principais. Depende do limiar, que é F2 nos modelos e 0,5 nos baselines, então não é comparável. |

Registrar essas ausências segue a regra do prompt ("calcule-as ou registre-as como ausentes")
e a prioridade do responsável de evitar verificações sem efeito na decisão.

## 5. Matriz de decisão

**Definição dos estados, fixada antes da aplicação:**

- `aprovado_para_teste`: o candidato passa todas as margens e proteções do §11, sem lacuna de
  conformidade.
- `baseline_preferido`: o candidato conforme ao protocolo falha os critérios, e o baseline
  válido é a entrega.
- `inconclusivo`: a evidência é insuficiente, sem lacuna de implementação.
- `inelegivel`: há falha fatal (vazamento, não convergência, previsão inválida ou métrica
  ausente).
- `requer_2d`: uma lacuna de implementação ou de conformidade impede conclusão válida sobre a
  hipótese aprovada.

| Fonte | Tarefa | Estado | Comparador (piso) | Melhor candidato na 2B | Evidência principal | Limitações |
|---|---|---|---|---|---|---|
| Eólica | corte_positivo | `requer_2d` | `historico`, AP 0,6896 | LightGBM 0,5250 | −0,164 de AP médio; 0/4 rodadas; §2.1 | §6 |
| Eólica | restricao_registrada | `requer_2d` | `historico`, AP 0,7305 | LightGBM 0,5818 | −0,149 de AP; 0/4; §2.1 | §6 |
| Eólica | volume (pipeline) | `requer_2d` | `mesmo_horario_dia_anterior` (na prática, frequência entidade×horário), MAE 15,86 | lgbm-lgbm 19,62 | MAE +24%; WAPE pior; §2.1 e §2.3 item 3 | §6 |
| Eólica | causa | `requer_2d` | `historico`, macro-F1 0,5298 | linear 0,4110 | −0,119; causa sem histórico de causa (§2.1); baselines de causa a corrigir (§2.2) | §6 |
| Solar | corte_positivo | `requer_2d` | `historico`, AP 0,7063 | LightGBM 0,6433 | −0,063; 1/4; Brier +0,030; §2.1 | §6 |
| Solar | restricao_registrada | `requer_2d` | `historico`, AP 0,7699 | LightGBM 0,7334 | −0,037; 1/4; Brier +0,037; §2.1 | §6 |
| Solar | volume (pipeline) | `requer_2d` | `mesmo_horario_dia_anterior`, MAE 15,06 | lgbm-lgbm 20,41 | MAE +35%; `n_estimators=1` em V3/V4; Gamma linear extrapola | §6 |
| Solar | causa | `requer_2d` | `ultimo_valor`, macro-F1 0,4786 | linear 0,4126 | −0,066; 1/4; §2.1 e §2.2 | §6 |

**Por que não `baseline_preferido`?** Esse estado conclui que um modelo conforme não superou o
baseline. Aqui o modelo avaliado não era o do protocolo. Se a 2D, com as features aprovadas,
ainda não superar o piso, a célula passa a `baseline_preferido`. É o desfecho mais provável
para a causa e, possivelmente, para o volume, mas isso não pode ser decidido agora.

**Recomendações preliminares da 2B:** nenhuma foi usada como autoridade.

## 6. Receita, teste reservado e o que fica congelado agora

- **Receita para o teste:** **não congelada.** Não há candidato aprovado nem receita conforme
  a confirmar.
- **Teste reservado (maio–agosto/2026): permanece bloqueado.**
  - Abri-lo agora para "confirmar o baseline" e, depois da 2D, de novo para os candidatos
    faria do teste um seletor entre alternativas, o que é vedado pelo §6.3.
  - Ele será aberto uma única vez, depois que a 2D terminar e uma nova 2C congelar a receita,
    seja ela um modelo ou um baseline.
- **Congelado desde já, para impedir que o alvo se mova na 2D:**
  1. margens e proteções do §11, sem alteração;
  2. regra do comparador: melhor média V1–V4 entre os baselines **conformes ao §7.2**,
     recalculados na 2D, com uma única regra nas quatro rodadas; em empate numérico exato,
     vale a ordem `ultimo_valor`, `mesmo_horario_dia_anterior`, `mesmo_horario_recente`,
     `historico`;
  3. valores de referência da tabela 3.1. Se um comparador corrigido mudar de valor, os dois
     números serão reportados;
  4. teste reservado intocado.
- **Saída de demonstração até a 2D:**
  - ocorrência: o baseline `historico`;
  - volume: a frequência × média positiva entidade×horário (o `historico`, na prática igual ao
    comparador);
  - causa: a última causa reconhecida ou a distribuição histórica.
  - Deve ser apresentada como "baseline histórico validado retrospectivamente em V1–V4, sem
    teste independente". Não é modelo de IA aprovado.

## 7. Limitações que acompanham toda leitura

- Amostragem sistemática diária de `t0` (semente 42), só em initial/refit:
  - eólica: 4/48 nas ocorrências e 14/48 em volume e causa;
  - solar: 16/48 nas ocorrências; volume e causa completos;
  - a prevalência amostrada difere no máximo 0,0004 da completa.
- Baselines de ocorrência com limiar 0,5 e `threshold or 0.5` (não afetam AP, Brier nem o
  §11).
- Subconjunto de features (§2.1), elegibilidade por `t0` e volume condicional avaliado em todas
  as linhas.
- LightGBM:
  - avisos `LGBMDeprecationWarning`;
  - 6 threads determinísticas, diferente do piloto em 1 thread;
  - one-hot em vez de categorias nativas.
- Commits de código na máquina dedicada (§13.3); 2C executada no mesmo host.
- Sementes 17 e 101 e intervalo de volume não executados; origem e +72h não executados.
- Backtest retrospectivo de snapshot revisado, sob disponibilidade hipotética (§3.3).
- SHAP e outras explicações não foram produzidos. Nenhuma associação foi tratada como causa.

## 8. Valor para o usuário e para a apresentação

- **Achado de produto (fato, retrospectivo):** uma regra transparente, a frequência recente da
  própria usina naquele horário, já alcança em média AP 0,69–0,77 para ocorrência e MAE de
  cerca de 15 MWmed no volume. É um piso honesto e explicável para o gerador. Todo modelo
  precisa superá-lo para justificar complexidade.
- **Por que agora:** a prevalência de corte subiu muito de 2024 para 2025–2026 (refit 0,19
  contra calibração 0,48 na eólica V3). Isso favorece regras recentes e penaliza modelos que
  não enxergam o regime recente.
- **Limitação a declarar no pitch:** os modelos da 2B não representam a abordagem aprovada. A
  decisão sobre IA versus baseline depende da 2D. O teste independente ainda não foi usado.

## 9. Próximos passos

Executar a Etapa 2D conforme `docs/handoffs/stage2d-prompt.md`. Em seguida, uma nova rodada de
análise (2C′) aplica esta mesma matriz, congela a receita e decide o teste. O merge em `main`
continua não autorizado.
