# Handoff da nova Etapa 2 para a integração de domingo (27/09/2026)

> **Atualização de 26/09 (fim do dia):** o produto foi reduzido à previsão de ocorrência com
> causa histórica, sem volume nem faixas. Leia primeiro a seção 6 e
> `docs/decisao-foco-ocorrencia-causa.md`. As seções 1 a 5 ficam como registro. Onde elas
> falam de volume, faixas, `diario_hgb_v1/v3` ou 130 dias de histórico, vale a seção 6.

Branch: `etapa-2-nova-abordagem`, criada a partir de `origin/main`. O merge em `main` não foi
feito, porque depende de pedido do responsável. Os resultados estão em
`docs/reports/nova-abordagem/README.md`; a narrativa, nas entradas "Nova Etapa 2 (1/n…)" do
diário.

## 1. Mudanças que afetam as Etapas 3 e 4

1. **`RESERVED_TEST_START` agora é `2026-09-01`** (`src/curtamap/contracts.py`, commit
   `8633122`).
   - `etapa-3-recomendacao` (`recommendation.py`, testes do período reservado) e
     `etapa-4-interface` (`ui/operacao.py` limita `t0 <= 2026-04-30`) importam essa constante.
   - Ao integrar, os seletores de data e os testes que assumiam maio precisam aceitar datas até
     31/08/2026.
2. **`nightly_cutoff` usa o calendário de feriados**
   (`curtamap.previsao.calendario`, `configs/calendario-2023-2026.json`).
   - O corte fica igual ou mais conservador que antes, e nunca mais otimista.
   - No container, copie `configs/` ou defina `CURTAMAP_CALENDAR_PATH`.
   - O calendário cobre só 2023–2026. Datas fora desse intervalo levantam `ValueError`.
3. **Novo preditor do produto:** use `curtamap.previsao.produto.product_predictor()`.
   - Ela devolve o `DailyForecaster` com o modelo mais recente em `models/previsao/`.
   - Sem artefato, devolve o `SameSlotRecentBaseline`.
   - A interface `predict(history, t0, data_cutoff)` é a mesma do `Predictor`.
4. **Histórico exigido:** o preditor novo precisa de `HISTORY_DAYS` dias antes do corte: 92
   na v1 e **130 na v3** (ver seção 5). Importe a constante de `curtamap.previsao.produto`.
   A interface carrega hoje só 28 (`inicio = corte - timedelta(days=28)` em
   `ui/operacao.py`). Troque por `corte - timedelta(days=HISTORY_DAYS)`.
5. **Emissão recomendada:** às 20h de D, com `t0` = 00h de D + 1 e
   `data_cutoff = nightly_cutoff(20h de D)`.
   - Qualquer `t0` na grade de 30 min funciona, e as idades acompanham o corte:
     - com `t0` às 10h de D, `nightly_cutoff` dá corte em D − 2 (o fim de D − 2), e as idades
       ficam entre 2 e 3, dentro do intervalo de treino (2 a 7);
     - a idade 1 aparece se a UI usar o **instante da emissão** (20h de D) como `t0`, porque as
       meias-horas de D caem com idade 1, fora do treino. Isso é extrapolação, registrada em
       `idade_informacao_dias`.

     Por isso, use `t0` = 00h de D + 1.
   - `data_cutoff` precisa ser meia-noite.
6. **Colunas extras no `FORECAST_SCHEMA`** (permitidas pelo contrato):
   - `emitido_em`;
   - `idade_informacao_dias`;
   - `baseline_historico_28d`, a frequência histórica da usina no slot, útil para a UI mostrar
     "modelo contra regra simples";
   - `tipo_saida_volume` (`modelo` ou `baseline_historico_28d`);
   - `tipo_saida_causa` (`baseline_usina_28d`, `baseline_estado_7d` ou nulo).

   `tipo_saida` é `modelo` porque a ocorrência é o componente principal. **A UI deve mostrar
   a proveniência por componente**: a causa é sempre baseline e o volume eólico também.
7. **`instante_observacao` é nulo** (é um modelo) e `cenario_disponibilidade` é
   `diario_20h_dia_util_feriados`.

## 2. Artefatos e como regenerar (tudo fora do Git)

```bash
uv sync --dev
# Backtest jan–ago/2026 (~30 min, pico de ~1,5 GB) e resumo com decisão por célula e limiares
uv run python -m curtamap.previsao.avaliacao 2026-01 2026-08
uv run python -m curtamap.previsao.relatorio data/interim/previsao docs/reports/nova-abordagem
# Modelo congelado do produto (~4 min): models/previsao/diario_hgb_v1_2026-08-30.joblib
uv run python -m curtamap.previsao.treinar --limiares data/interim/previsao/limiares.json \
  --manifesto docs/reports/nova-abordagem/modelo-congelado.json
# Reprodução histórica para o dashboard (4 semanas de ago/2026, emissões diárias às 20h)
uv run python -m curtamap.previsao.reproducao 2026-08-03 2026-08-30 \
  --limiares data/interim/previsao/limiares_jan_abr.json
# Validação de setembro (já executada uma vez; não reabrir para ajustar a receita)
uv run python -m curtamap.previsao.setembro baixar|prever|avaliar --modelo <joblib>
```

Observações:

- O hiperparâmetro `random_state=0` é fixo, mas o HGB com múltiplas threads pode variar no
  último dígito. O SHA-256 do manifesto identifica o artefato gerado em 26/09.
- `reproducao_2026-08-03_2026-08-30.parquet` fica em `data/interim/previsao/`. O script
  também salva um modelo `diario_hgb_v1_2026-07-30.joblib`, treinado só com rótulos até 30/07 (último dia liberado na emissão de 02/08). Divulgação: o modelo da reprodução não viu agosto, mas a composição `SERVING` (qual componente é modelo ou baseline) foi escolhida com o backtest jan–ago, que inclui agosto. A reprodução tem 28 emissões e 315.072 linhas; AP de agosto de 0,920 (eólica) e 0,904 (solar), contra 0,904 e 0,865 do `historico`.
  `product_predictor()` escolhe o mais recente (`2026-08-30`).
- `limiares_jan_abr.json` é derivado de `docs/reports/nova-abordagem/limiares.json`
  (chave `jan_abr`).

## 3. Containerização

- A imagem precisa de `configs/` (ou de `CURTAMAP_CALENDAR_PATH`), `data/raw/` montado e
  `models/previsao/*.joblib` montado ou gerado no build.
- O treino roda em ~4 min num notebook de 8 GB.
- O scikit-learn precisa ser a mesma versão do `uv.lock`, porque o artefato é joblib.
- Não há dependência nova. O LightGBM não foi usado.

## 4. Pendências conhecidas

- **Merge:** o diário usa `merge=union`, e `contracts.py` e `forecasting.py` também mudaram
  aqui. Confira os conflitos com as Etapas 3 e 4.
- O experimento H5 (quanto valeria uma previsão meteorológica) está na seção 6 do relatório,
  se tiver sido concluído. É um oráculo e **nunca** uma feature do produto.
- **Candidatos futuros, não adotados:**
  - causa solar com HGB sem peso;
  - recalibração periódica;
  - previsão meteorológica real como feature.

## 5. v3: faixas de volume (26/09, noite)

Resultados e decisões nas entradas "Nova Etapa 2 (8/n)" a "(12/n)" do diário. Dados em
`docs/reports/nova-abordagem/v3/`.

- **O que mudou no produto:** só as faixas de volume. Ocorrência, volume, causa, limiares de
  alerta e `SERVING` são os da v1; o `p_corte` da v3 é idêntico ao da v1.
  - A frente B (regime nacional e grupo de restrição) não foi adotada.
  - A frente C (causa) também não: a moda da usina continua servida.
- **Artefato:** `models/previsao/diario_hgb_v3_2026-08-30.joblib`, com manifesto em
  `docs/reports/nova-abordagem/modelo-congelado-v3.json` (SHA-256, limiares, composição e
  commit da receita). `product_predictor()` prefere o v3, depois o v1, depois o baseline.
  Para regenerar (~6 min):

  ```bash
  uv run python -m curtamap.previsao.treinar --limiares data/interim/previsao/limiares.json     --faixas docs/reports/nova-abordagem/v3/faixas.json     --manifesto docs/reports/nova-abordagem/modelo-congelado-v3.json
  ```

  `data/interim/previsao/limiares.json` é a chave `final_jan_ago` de
  `docs/reports/nova-abordagem/limiares.json`.
- **Histórico exigido: 130 dias antes do corte.** O `historico` de faixa usa cada dia d dos
  28 até L com o `cap_91d` do seu próprio L(d).
- **Colunas extras novas** (permitidas pelo contrato):

  | Coluna | Significado |
  |---|---|
  | `p_faixa_sem_corte`, `p_faixa_leve`, `p_faixa_moderada`, `p_faixa_severa` | probabilidade da faixa da fração cortada na meia-hora (somam 1) |
  | `faixa_provavel` | faixa de maior probabilidade na meia-hora |
  | `tipo_saida_faixas` | proveniência por limiar, por exemplo `k0:modelo,k1:historico,k2:historico` |
  | `p_faixa_dia_*`, `faixa_provavel_dia`, `tipo_saida_faixas_dia` | o mesmo para a fração do dia inteiro da usina (constante dentro de usina × dia) |

  - **Faixas:** a fração é o volume sobre `cap_91d` (p99 da referência nos 91 dias até L).
    As faixas são sem corte (0), leve (0, k₁], moderado (k₁, k₂] e severo (> k₂), com os
    limiares de `v3/faixas.json`:
    - meia-hora: eólica 0,12/0,38 e solar 0,20/0,48;
    - diário: eólica 0,05/0,16 e solar 0,05/0,14.
  - **Composição:**
    - solar: modelo nos três limiares e nos dois níveis;
    - eólica: modelo só em k₀ ("haverá corte?"). k₁ e k₂ vêm da frequência histórica da
      usina, porque o modelo não venceu (a intensidade eólica depende do vento do dia-alvo).
- **Como a UI deve mostrar:**
  - mostre as probabilidades, não só a faixa mais provável;
  - mostre a proveniência por limiar;
  - não leia `p_faixa_dia_sem_corte` como frequência. O k₀ diário ordena bem (AP melhor que o
    `historico`), mas tem Brier pior, ou seja, é mal calibrado;
  - na eólica diária, a composição mista tem RPS pior que o `historico` puro (0,161 contra
    0,155 em jan–ago).
- **Setembro não foi usado na v3.** A confirmação exige dias novos (após 24/09/2026).

## 6. Foco em ocorrência e causa histórica (26/09, fim do dia)

Decisão e motivos em `docs/decisao-foco-ocorrencia-causa.md`. A seção 5 está descontinuada.

- **Preditor:** `product_predictor()` serve só `diario_ocorrencia_v1_*`. Artefatos
  `diario_hgb_v1/v3` são ignorados. Sem artefato, volta ao `SameSlotRecentBaseline`.
- **Saídas:**
  - `p_corte`, `alerta` e `limiar_alerta` vêm do modelo, com os mesmos limiares da v1;
  - `p_causa_*` e `causa_prevista` vêm do histórico, com `tipo_saida_causa`;
  - `p_restricao` e `origem_prevista` são baselines, como antes;
  - volume e energia ficam nulos, com `tipo_saida_volume = "nao_previsto"`.
- **Contrato:** volume nulo não exige mais `motivo_sem_previsao`. A ausência de previsão é
  só `p_corte` nulo.
- **Histórico exigido:** `HISTORY_DAYS` = 92.
- **Artefato:** `models/previsao/diario_ocorrencia_v1_2026-08-30.joblib`, com manifesto em
  `docs/reports/nova-abordagem/modelo-congelado-ocorrencia.json`. Para regenerar (cerca de
  1 min):

  ```bash
  uv run python -m curtamap.previsao.treinar --limiares data/interim/previsao/limiares.json \
    --manifesto docs/reports/nova-abordagem/modelo-congelado-ocorrencia.json
  ```

- **Reprodução para o dashboard:** o comando da seção 2 continua válido e agora gera
  previsões sem volume.
- **Integração:** as Etapas 3 e 4 precisam deixar de depender de energia e da banda p10–p90.
  A lista de arquivos está na seção 5 do documento de decisão.
- **Recuperação:** tag `arquivo/etapa-2-v3-faixas` para a v3 e commit `7ee94f4` para a v1
  com volume.
- **Atenção ao relatório:** rodar `relatorio` com saída em `docs/reports/nova-abordagem`
  sobrescreve `metricas_backtest.csv` e `decisao_celulas.csv` sem as colunas de volume e do
  modelo de causa, que são a evidência da v1. Grave novas execuções em uma subpasta.
