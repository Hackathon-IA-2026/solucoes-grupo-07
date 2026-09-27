# CurtaMap: painel Streamlit (porta 8501) e rotina diária do aviso no mesmo contêiner.
#
# A imagem é autossuficiente: leva o modelo congelado e os avisos já emitidos, e a rotina
# baixa a publicação pública do ONS às 19h30 e emite o aviso de amanhã às 20h (Brasília).
# Não precisa de credenciais AWS nem de volume; se o contêiner reiniciar, a rotina emite de
# novo os dias que faltarem.
#
#   docker build -t curtamap .
#   docker run --rm -p 8501:8501 curtamap

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    CURTAMAP_DATA_DIR=/app/data \
    CURTAMAP_MODEL_DIR=/app/models \
    TZ=America/Sao_Paulo

# 1. Dependências com as versões do uv.lock (o scikit-learn precisa ser o do treino).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 2. Código, configurações e tema do painel.
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY configs/ ./configs/
COPY .streamlit/ ./.streamlit/
RUN pip install --no-cache-dir --no-deps .

# 3. Modelo servido e avisos já emitidos (base que a rotina vai completando).
COPY models/previsao/diario_ocorrencia_v1_2026-08-30.joblib \
     models/previsao/diario_ocorrencia_v1_2026-08-30.json \
     /app/models/previsao/
COPY data/processed/avisos.parquet /app/data/processed/

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4)"]

# 4. Rotina diária em segundo plano e painel em primeiro plano.
CMD ["sh", "-c", "python -m curtamap.previsao.ao_vivo --loop & exec streamlit run src/curtamap/app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false"]
