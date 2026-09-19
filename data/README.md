# Dados locais

Os dados nao sao versionados neste repositorio.

- `raw/`: Parquet originais, imutaveis.
- `interim/`: recortes e tabelas intermediarias reproduziveis.
- `processed/`: features e conjuntos de treino reproduziveis.

Registre origem, data de download, checksum e periodo de cada arquivo. Na base integrada, use sempre `fonte + id_ons` como identificador.

## Download automatizado

```bash
uv sync --extra data --dev
uv run python -m curtamap.download_data --list
uv run python -m curtamap.download_data
```

O comando padrão baixa somente os Parquet do ONS. Arquivos existentes são preservados para evitar transferências e sobrescritas acidentais.
