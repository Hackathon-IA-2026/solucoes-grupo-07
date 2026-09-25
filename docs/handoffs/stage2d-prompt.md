# Prompt autossuficiente para a Etapa 2D

Execute exclusivamente a Etapa 2D do CurtaMap: corrigir as lacunas de conformidade que a
Etapa 2C encontrou na implementação da 2B e reexecutar a comparação V1–V4 com os candidatos
que o protocolo aprovou. Não abra, não gere features e não pontue o teste reservado
(maio–agosto/2026). Não escolha vencedor: a decisão fica para a análise seguinte (2C′), que
aplica a matriz da 2C já congelada.

Responda em português do Brasil. Trabalhe na branch `etapa-2-experimental`, sem merge e sem
push. Use TDD (Red–Green–Refactor), commits atômicos em Conventional Commits e o diário
append-only.

## 1. Leitura obrigatória

- `AGENTS.md` e `docs/experimental-protocol.md` (§5, §7, §8, §9, §10, §11 e §12).
- `docs/reports/stage2c/decision.md`: decisão, achados de conformidade, comparadores e valores
  congelados. **É a fonte principal desta etapa.**
- `docs/reports/stage2c/matriz-2c.json` e `auditoria-baselines-2c.json`.
- `docs/reports/stage2b/execution-report.md` e `experiments/stage2b/README.md` (raiz, junção e
  proibição de `git clean -x`).
- As entradas do diário de 24/09/2026, incluindo a da 2C.
- `src/curtamap/experimental/`, principalmente `runner.py`, `models.py`, `training.py`,
  `baselines.py`, `campaign.py` e `metrics.py`.

## 2. Versão do protocolo antes de qualquer execução

Antes de alterar código, acrescente ao protocolo uma seção **"Versão 2 — Etapa 2D"**, sem
reescrever o texto aprovado. Ela deve:

1. **Registrar que V1–V4 já foram vistas.** As correções abaixo são conformidade ao
   protocolo aprovado, motivadas por auditoria de código, e não busca orientada por
   resultado. Mesmo assim, a evidência V1–V4 da 2D não é "cega", e a alegação independente
   fica só para o teste reservado.
2. **Manter sem alteração:**
   - as margens e proteções do §11;
   - a regra do comparador (melhor média V1–V4 entre baselines conformes ao §7.2, com uma
     única regra; empate exato pela ordem `ultimo_valor`, `mesmo_horario_dia_anterior`,
     `mesmo_horario_recente`, `historico`);
   - as grades do §9.1, as rodadas, o calendário, os datasets e a semente 42.
3. **Listar cada mudança deste prompt com motivo e evidência.** Toda mudança que não seja pura
   conformidade exige decisão explícita do responsável **antes** da execução real. Registre
   quem decidiu e quando.

## 3. Correções de conformidade (obrigatórias)

### 3.1 Features do §8, iguais entre famílias

Substitua `NUMERIC_FEATURES`/`CATEGORICAL_FEATURES` por uma lista versionada, usada pelas duas
famílias. As colunas já existem nos `features.parquet` de `stage2b-datasets`; **não regenere
datasets** para esta etapa.

- **Calendário:** `horizon`, `t0_hour_sin`, `t0_hour_cos`, `tau_hour_sin`, `tau_hour_cos`,
  `t0_weekday`, `t0_month`, `t0_day_of_year`, `tau_weekday`, `tau_month`, `tau_day_of_year` e
  o indicador de fim de semana/feriado de `tau` pelo calendário congelado
  (`tau_weekend_or_holiday`, derivado na campanha como hoje, não lido do dataset).
- **Cadastro (categóricas):** `id_ons`, `id_estado`, `id_subsistema`, `ceg_level`.
- **Histórico próprio:**
  - `last_positive`, `last_restriction`, `last_volume_mwmed`;
  - `last_cause` (categórica);
  - `history_{30m,1h,24h,48h,7d}_{positive,volume}`.
- **Mesmo horário:** `same_hour_{1,2,3,7}d_{positive,volume}`.
- **Estatísticas móveis:**
  - `positive_frequency_{24h,7d,28d}`;
  - `{mean,std,max}_volume_{24h,7d,28d}`;
  - `restriction_frequency_28d`;
  - `cause_{rel,cnf,ene}_share_28d`.
- **Agregados:** `state_positive_frequency_28d` e `subsystem_positive_frequency_28d`.
- **Episódio:** `observed_episode_length`, `hours_since_positive` e `hours_since_restriction`.
- **Cobertura e idade:** `history_coverage_28d` e `history_age_hours`.

**Nunca usar como feature:** `t0`/`tau` brutos, `fonte`, `eligible_history` (é filtro),
`target_observed`, `true_*` e `target_available_at`.

**Lacunas de dataset:** o §8 também menciona composição de causa e frequência de restrição em
24h/7d e média regional de volume. Essas colunas não existem nos datasets. Registre-as como
lacuna conhecida; não as implemente sem decisão do responsável, porque exigiriam regenerar os
datasets (cerca de 6 h com verificação).

**Testes, antes da implementação:**

- a lista contém cada família do §8;
- nenhuma coluna proibida entra;
- a lista é igual entre famílias;
- um contrato lê o schema real de uma partição e falha se alguma coluna faltar.

### 3.2 Ausências e categorias (§8 e §9.1)

- **Linear:**
  - mediana aprendida no treino **mais um indicador de ausência** por coluna numérica ou
    booleana com nulos;
  - padronização só no treino;
  - one-hot esparso com `<MISSING>`/`<UNKNOWN>`, como hoje.
- **LightGBM:**
  - tratamento nativo de ausências (sem imputar);
  - categorias nativas (códigos inteiros com dicionário do treino e categoria desconhecida
    explícita);
  - matriz numérica densa `float32`, não CSR.
- **Se as categorias nativas se mostrarem inviáveis** (por exemplo, pela cardinalidade de
  `id_ons`): registre a medição e mantenha o one-hot como desvio explícito.
- **Testes:**
  - o indicador existe e só é aprendido no treino;
  - uma categoria nova vira desconhecida;
  - o joblib recarregado prevê o mesmo que o objeto em memória.

### 3.3 Baselines de causa (§7.2)

Corrija `baselines.py`:

- **`mesmo_horario_dia_anterior`:** causa da ordem reconhecida em `tau − 24h`, se disponível
  em `t0`; senão, o fallback estatístico identificado.
- **`mesmo_horario_recente`:** última ordem reconhecida no horário de `tau` em até 28 dias;
  senão, o fallback.
- **`ultimo_valor`:** última causa reconhecida em 28 dias; senão, a **majoritária** do
  fallback (hoje devolve `CNF`).

**Onde recalcular:** os baselines estão dentro dos datasets. Prefira recalcular só a causa dos
baselines nas janelas de validação V1–V4 e de calibração, num artefato separado versionado
por commit, com teste de paridade contra o oráculo corrigido. Não sobrescreva
`stage2b-datasets`.

**Testes com fixtures sintéticas:**

- ordem em `tau − 24h` presente e ausente;
- ordem mais recente no mesmo horário;
- ausência de causa conhecida;
- a linha só pode ser usada depois de liberada.

### 3.4 Limiar dos baselines de ocorrência (§7.2)

- Aplique aos baselines probabilísticos (`historico` e os fallbacks) o mesmo procedimento F2
  no trecho interno de calibração de cada rodada.
- Os baselines 0/1 mantêm o limiar 0,5, identificado.
- Remova `threshold or 0.5`: um limiar ausente precisa ser explícito, e 0,0 não pode virar 0,5.
- Isso muda só métricas dependentes de limiar. AP e Brier ficam iguais, e os testes devem
  provar isso.

### 3.5 Volume

- Registre para cada modelo: `n_iter_`, `best_iteration_`, a métrica de parada e a curva
  interna.
- **Métrica de *early stopping* do LightGBM Gamma:** hoje é L1, o que levou a
  `n_estimators=1` na solar V3/V4. A troca pela deviance Gamma (coerente com o §5.2, que estima
  média condicional) **não é conformidade pura**. Proponha a mudança no protocolo v2 com essa
  justificativa e execute só depois da decisão do responsável. Sem decisão, mantenha L1 e
  reporte o efeito.
- **Gamma linear:** registre o máximo de previsão e a fração de linhas de validação fora da
  faixa de features do treino. Não introduza teto ou recorte de previsão sem nova versão do
  protocolo aprovada.

### 3.6 Métricas e relatórios (§10 e §13.2)

- Todo nulo sai com `reason` (`classe_unica`, `sem_suporte`, `denominador_zero`,
  `recorte_vazio`).
- A sensibilidade `noturno_mais_24h` calcula baselines, os 64 recortes e os diagnósticos de
  volume.
- Os recortes de idade usam a **mesma população** para modelo e baseline, com a idade das
  features. A idade do comparador fica só como recorte adicional com outro nome.
- Reporte a incoerência `P(corte_positivo) > P(restricao_registrada)` por rodada.

### 3.7 Agregações do §10.2 e do §10.3 (obrigatórias nesta etapa)

Implemente-as com testes sintéticos e calcule-as nas runs novas:

1. **Visão por entidade com peso igual:** WAPE agregado e média de WAPEs por entidade, com os
   nomes distintos; suporte e exclusões explícitos.
2. **Energia diária:** somente a emissão das 00h, soma das 48 janelas × 0,5 MWh, em dias com
   verdade completa.
3. **Bootstrap de blocos de 7 dias:** diferenças semanais pareadas candidato − comparador,
   1.000 reamostragens, semente 42, estratificado por rodada e com peso igual entre rodadas;
   IC 95%. Informe o número de blocos e as semanas parciais.
4. **Interseção comparável principal × +24h,** com a cobertura perdida fora dela.
5. **Recall nas primeiras janelas de episódio e persistência na primeira janela zero,** por
   horizonte, com o limiar próprio de cada origem já corrigido (§3.4).
6. **Contribuição das dez entidades e dos dez episódios de maior erro.**

## 4. Recursos: medir antes de treinar

A 2B atingiu picos de 24,06 GiB com 12 features. A lista do §3.1 multiplica por cerca de 5 as
colunas numéricas.

1. Aplique antes as reduções do §12.2:
   - `float32`;
   - numérica densa em vez de CSR;
   - liberar os splits depois de construir o `Dataset` do LightGBM;
   - evitar cópias entre Polars, NumPy e SciPy.
2. Meça com um piloto técnico por fonte (StepId novo, até 500 mil exemplos, sem métricas de
   seleção) e projete o pico da rodada mais pesada.
3. Se a taxa de amostragem de `t0` precisar mudar (hoje, eólica 4/48 e 14/48; solar 16/48 e
   48/48):
   - fixe as novas taxas **antes** da validação externa, pela regra da 2B (maior fração com
     pico projetado ≤ 20 GiB);
   - use o mesmo método `t0_sistematico_diario_v1` e a mesma semente;
   - registre como desvio.
4. Não execute runs em paralelo nem use o teste reservado.

## 5. Execução

1. **Testes, lint e revisão antes das runs reais:**
   - `uv run pytest`;
   - `uv run ruff check .`;
   - `uv run ruff format --check .`;
   - verificação de paridade dos baselines corrigidos.
2. **Runs principais V1–V4 das duas fontes**, com `run_id` novos (`main2d-<fonte>-v<N>-001`).
3. **Sensibilidades +24h congeladas** (`delay2d-…`).
4. **Integridade:** `checksums.json` e atualização de `execucao/run-index.json`. As runs da 2B
   ficam intactas.
5. **Análise:** rode `scripts/stage2c/analisar_matriz_2c.py`, adaptado aos novos `run_id` por
   parâmetro e sem editar os números congelados, para produzir a matriz nova ao lado da
   antiga.
6. **Extensões recomendadas, só com o mínimo completo:** sementes 17 e 101 e o intervalo de
   volume do §9.3, sem mudar configuração.

**Orçamento de referência** (medido na 2B, com 12 features): cerca de 11 h das principais e
2,3 h das sensibilidades. Reprojete após o piloto.

## 6. Entrega

- Relatório factual `docs/reports/stage2d/execution-report.md`, sem escolher vencedor:
  - proveniência (commits, hashes, configuração, sementes);
  - desvios e populações;
  - tabelas V1–V4;
  - comparadores recalculados, reportando lado a lado os valores congelados da 2C e os
    corrigidos;
  - agregações do §3.7, custos e falhas.
- Entrada no diário (fatos, interpretações, alternativas, decisões, limitações e próximos
  passos).
- Prompt para a análise seguinte (2C′), que:
  - aplica a matriz e os estados definidos em `docs/reports/stage2c/decision.md` (§5);
  - congela a receita, seja ela modelo ou baseline;
  - só então decide abrir o teste reservado, uma única vez.

## 7. Proibições

- Abrir, gerar features ou pontuar maio–agosto/2026.
- Mudar margens, grades, candidatos, rodadas ou comparadores para resgatar médias.
- Apagar tentativas falhas, resultados negativos ou as runs da 2B.
- Fazer `git clean -x`/`-X` (a junção levaria os dados reais).
- Fazer merge em `main` ou push sem pedido do responsável.
