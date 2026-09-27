# Dados locais

Os dados nao sao versionados neste repositorio.

- `raw/`: Parquet originais, imutaveis.
- `interim/`: recortes e tabelas intermediarias reproduziveis.
- `processed/`: features e conjuntos de treino reproduziveis.

Registre origem, data de download, checksum e periodo de cada arquivo. Na base integrada, use sempre `fonte + id_ons` como identificador.

## Download automatizado

```bash
uv sync --extra data --dev
uv run python -m zelo.download_data --list
uv run python -m zelo.download_data
```

O comando padrão baixa somente os Parquet do ONS. Arquivos existentes são preservados para evitar transferências e sobrescritas acidentais.

## Auditoria do snapshot

```bash
uv run python -m zelo.audit
uv run python -m zelo.audit --strict
```

O segundo comando retorna código 1 quando há achados. Consulte o
[contrato e a interpretação](../docs/data-contract.md). Os relatórios pequenos ficam
em `docs/reports/stage1/`; a auditoria nunca modifica os cinco arquivos originais.

## Validação pública e EDA

```bash
# Baixa os Parquet mensais atuais do ONS em data/interim/official/ (ignorado pelo Git)
uv run python -m zelo.public_reference
# Executa a EDA do início ao fim (também coberta por tests/test_notebook.py)
uv run jupyter execute --inplace notebooks/01_eda_fundamentos_dados.ipynb
uv run pytest tests/test_notebook.py
```

A publicação do ONS é revisada em pós-operação: os arquivos oficiais baixados podem
diferir do snapshot (ver `docs/target-definition.md`).
