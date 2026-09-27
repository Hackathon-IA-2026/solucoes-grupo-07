# CurtaMap

> O nome do produto ainda não é definitivo.

Aviso diário de cortes para usinas eólicas e solares. Toda noite, às 20h, mostra em quais horas do dia seguinte cada usina deve ser cortada, por qual motivo e quanto o aviso costuma acertar.

## Demo

- **Link da demo:** a definir

## Estado atual

- **Modelo:** um classificador por fonte (`diario_ocorrencia_v1`) calcula a chance de corte por usina e meia-hora do dia seguinte, com os dados do ONS liberados até a emissão das 20h.
- **Motivo:** vem da regra do histórico da usina (ordens das últimas 4 semanas naquele horário).
- **Painel:** tela única que lê os avisos já emitidos (`data/processed/avisos.parquet`). Mostra as janelas em alerta, as horas livres, o motivo e o acerto medido fora da amostra em setembro de 2026.
- **Demonstração:** os avisos exibidos são os de 01 a 25/09/2026, emitidos às 20h da véspera. De 01 a 24/09 o risco é o mesmo usado na validação; o de 25/09 foi emitido, mas ainda não tinha rótulo quando a validação foi feita. O painel não mostra o que aconteceu depois, como no uso real.
- **O que o aviso não diz:** quanto será cortado, quanto isso custa e se a ordem será mantida.

As decisões e perguntas em aberto estão em [docs/architecture.md](docs/architecture.md). O caminho de implementação está em [docs/roadmap.md](docs/roadmap.md).

## Stack

- Python 3.12 e `uv`
- Polars, DuckDB e Parquet para processamento
- scikit-learn e modelos tabulares candidatos para experimentação
- Streamlit para a interface (telas em `src/curtamap/ui/`, cálculos testados em `src/curtamap/painel/`)
- AWS com infraestrutura como código para build, execução, dados, modelos e observabilidade
- Bedrock ou NVIDIA NIM como camada opcional de explicação em linguagem natural

## Pré-requisitos

- Git
- [`uv`](https://docs.astral.sh/uv/) 0.12 ou superior
- Acesso à internet para instalar dependências e baixar as bases
- Espaço em disco compatível com os Parquet escolhidos
- Python 3.12, instalado automaticamente pelo `uv` quando necessário

Docker, Node/pnpm e AWS CLI só são necessários para o deploy; veja [docs/deploy.md](docs/deploy.md).

## Como executar

```bash
uv sync --extra data --dev
cp .env.example .env
uv run python -m curtamap.download_data                      # Parquet do ONS em data/raw/
uv run python -m curtamap.previsao.treinar --limiares data/interim/previsao/limiares.json   --manifesto docs/reports/nova-abordagem/modelo-congelado-ocorrencia.json
uv run python -m curtamap.previsao.setembro baixar           # publicação de setembro
uv run python -m curtamap.previsao.setembro prever --modelo models/previsao/<artefato>.joblib
uv run python -m curtamap.previsao.avisos --modelo models/previsao/<artefato>.joblib
uv run streamlit run src/curtamap/app.py
```

Sem o arquivo de avisos, o painel mostra como gerá-lo em vez de números.

As integrações opcionais podem ser instaladas com `uv sync --extra data --extra aws --extra infra --dev`.

Validações:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Dados

As bases oficiais podem ser listadas e baixadas automaticamente da pasta pública indicada no Caderno:

```bash
uv sync --extra data --dev
uv run python -m curtamap.download_data --list
uv run python -m curtamap.download_data
```

Por padrão, o script baixa somente os cinco Parquet do ONS para `data/raw/`. Use `--include-tutorials` para incluir também o material ERA5. Downloads existentes são preservados; use `--force` apenas quando quiser substituí-los.

O diretório é ignorado pelo Git. Consulte [data/README.md](data/README.md) para as convenções de dados.

## Licença

MIT. Consulte [LICENSE](LICENSE).
