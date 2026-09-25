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

## Receita congelada

*(a preencher no congelamento)*
