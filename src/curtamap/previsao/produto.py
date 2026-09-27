"""Ponto único de escolha do preditor do produto para a interface e a recomendação.

Usa o modelo diário mais recente em `models/previsao/` (treino mais novo); sem artefato
treinado, volta ao baseline provisório, que já é marcado como `baseline` no contrato.
O histórico passado a `predict` precisa cobrir `HISTORY_DAYS` dias antes do corte.
"""

from pathlib import Path

from curtamap.config import settings
from curtamap.forecasting import Predictor, SameSlotRecentBaseline
from curtamap.previsao.features import ENTITY_LOOKBACK_DAYS
from curtamap.previsao.modelo import MODEL_VERSION, DailyForecaster, DailyModel

# Janela mais longa das features (91 dias) mais o último dia liberado.
HISTORY_DAYS = ENTITY_LOOKBACK_DAYS + 1


def latest_model_path(model_dir: Path = settings.model_dir) -> Path | None:
    # O nome termina na data do último rótulo (ISO), então a ordem lexical é cronológica.
    candidates = sorted((Path(model_dir) / "previsao").glob(f"{MODEL_VERSION}_*.joblib"))
    return candidates[-1] if candidates else None


def product_predictor(model_dir: Path = settings.model_dir) -> Predictor:
    path = latest_model_path(model_dir)
    return DailyForecaster(DailyModel.load(path)) if path else SameSlotRecentBaseline()
