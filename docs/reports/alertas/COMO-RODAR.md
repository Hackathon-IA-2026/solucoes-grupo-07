# Reproduzir a entrega local

Na raiz da branch `codex/alertas-impacto-negocio`, use Python 3.12 e o lock versionado:

```powershell
uv sync --dev --frozen
$env:OMP_NUM_THREADS = '2'
$env:POLARS_MAX_THREADS = '2'
$env:PYTHONIOENCODING = 'utf-8'
```

Nesta máquina, `uv.exe` está em `../solucoes-grupo-07/.tools/bin/uv.exe`. Se necessário,
use esse caminho no lugar de `uv`; o ambiente `.venv` desta branch já foi instalado.
O instalador automático de Python teve uma falha de link no Windows; foi resolvida
indicando ao `uv sync --python` o Python 3.12 já disponível no runtime local.

## Dados e replay

Os dois Parquet principais do snapshot ficam em `data/raw`; se já estão em outro
checkout, use `-Dados` para reaproveitá-los. Não é necessário copiá-los nem baixar os detail.

```powershell
# Aqui as bases já estão no checkout vizinho.
./scripts/rodar-alertas.ps1 -Fonte fotovoltaica -Dados '../solucoes-grupo-07/data'
./scripts/rodar-alertas.ps1 -Fonte eolica -Dados '../solucoes-grupo-07/data'
```

O script limita duas threads, 3 GiB de memória privada somada da árvore de processos e
20 minutos por fonte. A amostragem é de aproximadamente 1 segundo: o limite pode ser
ultrapassado entre amostras antes da interrupção. Executa uma fonte por vez e salva logs.

Alternativa multiplataforma, sem o monitor de recursos PowerShell:

```bash
uv run python -m curtamap.previsao.alertas 2026-08-01 2026-08-31 --fonte fotovoltaica --dados data
uv run python -m curtamap.previsao.alertas 2026-08-01 2026-08-31 --fonte eolica --dados data
```

Baixe o recurso `pld_horario_2026` no
[catálogo oficial da CCEE](https://dadosabertos.ccee.org.br/dataset/pld_horario) e salve em
`data/interim/ccee/pld_horario_2026.csv`. Nesta execução o terminal foi bloqueado pelas
políticas HTTPS da CCEE; o download normal pelo navegador funcionou, sem login.
Preserve o arquivo: a publicação pode mudar. O manifesto versionado registra o SHA-256
da revisão utilizada. Não há credenciais neste fluxo.

```powershell
uv run python -m curtamap.alertas_negocio --replay data/interim/alertas/fotovoltaica_2026-08-01_2026-08-31.parquet --pld data/interim/ccee/pld_horario_2026.csv --dados ../solucoes-grupo-07/data
uv run python -m curtamap.alertas_negocio --replay data/interim/alertas/eolica_2026-08-01_2026-08-31.parquet --pld data/interim/ccee/pld_horario_2026.csv --dados ../solucoes-grupo-07/data
uv run python scripts/relatorio_alertas.py
```

## Abrir a demonstração

```powershell
uv run streamlit run src/curtamap/alertas_app.py --server.address 127.0.0.1 --server.port 8517 --browser.gatherUsageStats false
```

Abra [o painel local](http://127.0.0.1:8517). É uma demonstração de agosto/2026, não
emissão operacional para amanhã. Ele usa Parquet já calculado e não retreina na navegação.

- Escolha fonte/reprodução, dia, UF e usina.
- Veja as 48 probabilidades e o limiar congelado.
- Confira causa histórica, período liberado e tamanho da amostra.
- Compare o horário de manutenção com os três baselines; varie preço e fração parada.
- Confira o resultado total, inclusive perdas, e exporte prioridades/janelas.

Pastas alternativas: `CURTAMAP_ALERTAS_DIR` e `CURTAMAP_NEGOCIO_DIR`.
O pipeline padrão `product_predictor()` e a entrada `app.py` permanecem separados deste
adaptador explícito para não mudar o trabalho paralelo de integração.

## Verificações

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Os testes usam fixtures pequenas identificadas como sintéticas; resultados de negócio
e ocorrência dos relatórios vêm dos dados reais. O teste que reexecuta a EDA completa
é pulado quando não há Parquet no `data/raw` deste checkout, mesmo que existam no vizinho.
Não é necessário repetir essa EDA para o pivô; os recortes reais acima foram executados.
