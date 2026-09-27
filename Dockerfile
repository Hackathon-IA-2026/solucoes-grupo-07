# CurtaMap: interface Streamlit na porta 8501.
#
# Dados e modelos NÃO entram na imagem. Na inicialização, `curtamap.s3_sync` baixa
# CURTAMAP_DATA_S3_URI -> $CURTAMAP_DATA_DIR/processed (avisos emitidos) e CURTAMAP_MODEL_S3_URI ->
# $CURTAMAP_MODEL_DIR/previsao, se definidos; sem eles, monte os diretórios como volume.
#
#   docker build -t curtamap .
#   docker run --rm -p 8501:8501 -v "$PWD/data:/app/data" -v "$PWD/models:/app/models" curtamap

FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CURTAMAP_DATA_DIR=/app/data \
    CURTAMAP_MODEL_DIR=/app/models \
    CURTAMAP_CALENDAR_PATH=/app/configs/calendario-2023-2026.json

WORKDIR /app

# Dependências primeiro, para aproveitar o cache de camadas; o extra aws traz o boto3.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --extra aws --no-install-project

COPY src ./src
COPY configs ./configs
RUN uv sync --frozen --no-dev --extra aws \
    && useradd --create-home --uid 1000 curtamap \
    && mkdir -p /app/data/raw /app/models/previsao \
    && chown -R curtamap:curtamap /app/data /app/models

USER curtamap
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4)"]

CMD ["sh", "-c", "python -m curtamap.s3_sync && exec streamlit run src/curtamap/app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false"]
