# Handoff da nova Etapa 2 para a integração de domingo (27/09/2026)

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
4. **Histórico exigido:** o preditor novo precisa de `HISTORY_DAYS` = 92 dias antes do corte.
   A interface carrega hoje só 28 (`inicio = corte - timedelta(days=28)` em
   `ui/operacao.py`). Troque por `corte - timedelta(days=HISTORY_DAYS)`.
5. **Emissão recomendada:** às 20h de D, com `t0` = 00h de D + 1 e
   `data_cutoff = nightly_cutoff(20h de D)`.
   - Qualquer `t0` na grade de 30 min funciona. Com `t0` de manhã, a primeira parte do
     horizonte tem idade de 1 dia, fora do intervalo de treino (2 a 7). É extrapolação,
     registrada em `idade_informacao_dias`.
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
  também salva um modelo `diario_hgb_v1_2026-07-30.joblib`, treinado só com rótulos até 30/07 (último dia liberado na emissão de 02/08). A reprodução tem 28 emissões e 315.072 linhas; AP de agosto de 0,920 (eólica) e 0,904 (solar), contra 0,904 e 0,865 do `historico`.
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
