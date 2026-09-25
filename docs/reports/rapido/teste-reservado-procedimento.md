# Teste reservado: procedimento de abertura única (25/09/2026)

**Autorização:** o responsável autorizou em 25/09, de manhã, a abertura do teste reservado
(maio–agosto/2026) **uma única vez**, no fim do dia, depois de congelar a receita por célula.

## 1. Congelar (antes de qualquer leitura do período reservado)

1. Preencher a tabela "Receita congelada" abaixo, célula por célula, com base nos resultados
   de V1–V4, na simplicidade (`s01`) e no estado sistêmico (`sys`).
2. Commitar este arquivo. O hash desse commit é o `--decision-ref`.
3. Depois do congelamento, nenhuma receita muda por causa do resultado do teste (§11.3: "não
   promover segundo colocado usando o mesmo teste como seleção").

## 2. Gerar as features do período reservado

Os alvos já estão em `experiments/stage2b/cache/stage2b/targets` até 08/2026. Rodar com o
ambiente de `experiments/stage2b/env.ps1` (`CURTAMAP_CACHE_DIR` e `CURTAMAP_EXPERIMENT_DIR`):

```bash
uv run curtamap-experiment --config configs/experimental/stage2b.example.json build-features \
  --scenario noturno_dia_util --source fotovoltaica --round reserved \
  --start 2026-05-01T00:00:00 --end 2026-09-01T00:00:00
uv run curtamap-experiment --config configs/experimental/stage2b.example.json build-features \
  --scenario noturno_dia_util --source eolica --round reserved \
  --start 2026-05-01T00:00:00 --end 2026-09-01T00:00:00
```

## 3. Pontuar uma vez

Para cada célula, repetir o comando do modelo FINAL da receita congelada, com um novo
`run_id` com o sufixo `-reservado` e mais estas opções:

```
--allow-reserved-test --decision-ref <hash do commit do §1>
```

- **O treino é determinístico** (`deterministic=True`, semente 42). Confere-se que o modelo é
  idêntico ao FINAL já salvo, comparando `booster_.model_to_string()`.
- **A validação usa só `round=reserved`.**
- **Nas células cuja receita é o baseline,** o mesmo comando fornece as métricas do baseline
  nas mesmas linhas.

## 4. Registrar

- **Tabela no relatório:** célula × receita × métrica do modelo × baseline × IC semanal.
- **Leitura:** confirma ou veta a receita, sem trocá-la.
- **Diário e commits:** registrar o resultado.

## Receita congelada (25/09/2026, ~13h; decisão do responsável: "pelas regras")

Congelada depois de todas as análises de V1–V4 do dia e antes de gerar qualquer feature do
período reservado. Nenhuma variante (`s01`, `sys`, recalibração) é pontuada no teste.

| Célula | Receita | Comparador | Estado §11 em V1–V4 |
|---|---|---|---|
| Corte solar | **modelo 003** | `historico` | AP aprovado (+0,062, 4/4); Brier médio falha (+0,017 > 0,01): `requer_analise` |
| Causa eólica | **modelo 005** | `historico` | margens aprovadas (+0,056, 3/4); IC semanal contém zero em V2/V3 |
| Corte eólico | baseline `historico` | — | modelo não aprovado (+0,023, 2/4) |
| Volume solar | baseline `historico` | — | modelo não aprovado (−4,97%; V2 +14%) |
| Volume eólico | baseline `mesmo_horario_dia_anterior` | — | modelo não aprovado (+0,1%) |
| Causa solar | baseline `ultimo_valor` | — | modelo não aprovado (+0,009, 2/4) |

**Previsões escritas antes do teste (falseáveis):**

1. **Corte solar:** o AP da 003 fica ≥ ao do `historico`. Se a prevalência de maio–agosto de
   2026 saltar como em 2025, o Brier da 003 fica **pior** que o do `historico`, porque o
   calibrador congelado subestima o nível.
2. **Causa eólica:** o macro-F1 da 005 fica ≥ ao do `historico`. Nos meses de alta do corte
   (padrão da V2), o ganho pode ser próximo de zero.
3. **Células de baseline:** o teste reporta apenas o baseline da receita. Os números do modelo
   que aparecem como subproduto são **diagnóstico**, não candidatos (§11.3).

**Comandos de pontuação** (o `<ref>` é o hash deste commit; cada célula, uma única vez):

```
uv run python scripts/rapido/treinar_contexto.py --source fotovoltaica --round FINAL --task corte_positivo --slots 4 --drop t0_month,t0_day_of_year,tau_month,tau_day_of_year --run-id rapido-fv-final-corte-003-reservado --allow-reserved-test --decision-ref <ref>
uv run python scripts/rapido/treinar_contexto.py --source eolica --round FINAL --task causa --slots 4 --chunk-days 7 --drop t0_month,t0_day_of_year,tau_month,tau_day_of_year --params '{"class_weight":"balanced"}' --run-id rapido-eol-final-causa-005-reservado --allow-reserved-test --decision-ref <ref>
uv run python scripts/rapido/treinar_contexto.py --source fotovoltaica --round FINAL --task volume_total --slots 4 --offset --no-categorical --drop t0_month,t0_day_of_year,tau_month,tau_day_of_year --run-id rapido-fv-final-voltot-004-reservado --allow-reserved-test --decision-ref <ref>
uv run python scripts/rapido/treinar_contexto.py --source fotovoltaica --round FINAL --task causa --slots 8 --drop t0_month,t0_day_of_year,tau_month,tau_day_of_year --params '{"class_weight":"balanced"}' --run-id rapido-fv-final-causa-005-reservado --allow-reserved-test --decision-ref <ref>
uv run python scripts/rapido/treinar_contexto.py --source eolica --round FINAL --task volume_total --slots 2 --chunk-days 7 --offset --no-categorical --drop t0_month,t0_day_of_year,tau_month,tau_day_of_year --run-id rapido-eol-final-voltot-004-reservado --allow-reserved-test --decision-ref <ref>
uv run python scripts/rapido/treinar_contexto.py --source eolica --round FINAL --task corte_positivo --slots 2 --chunk-days 7 --drop t0_month,t0_day_of_year,tau_month,tau_day_of_year --run-id rapido-eol-final-corte-003-reservado --allow-reserved-test --decision-ref <ref>
```

O último comando (cerca de 25 GiB) serve só para obter o `historico` do corte eólico nas mesmas
linhas. Roda por último, sozinho, com monitor de memória.
