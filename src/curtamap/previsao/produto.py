"""Ponto único de escolha do preditor do produto para a interface e a recomendação.

Preferência explícita: o modelo v3 mais recente (com faixas), depois o v1 mais recente em
`models/previsao/`; sem artefato treinado, volta ao baseline provisório, que já é marcado
como `baseline` no contrato. O histórico passado a `predict` precisa cobrir `HISTORY_DAYS`
dias antes do corte.
"""

from pathlib import Path

from curtamap.config import settings
from curtamap.forecasting import Predictor, SameSlotRecentBaseline
from curtamap.previsao.features import ENTITY_LOOKBACK_DAYS
from curtamap.previsao.modelo import MODEL_VERSION, DailyForecaster, DailyModel

VERSIONS = ("diario_hgb_v3", MODEL_VERSION)
# v3: o `historico` de faixa usa os dias (L − 28, L], cada um com o `cap_91d` e as features
# do seu próprio L(d), até 7 dias antes: 28 + 7 + 91 dias de janela, com folga.
HISTORY_DAYS = max(ENTITY_LOOKBACK_DAYS + 1, 130)


def latest_model_path(model_dir: Path = settings.model_dir) -> Path | None:
    # O nome termina na data do último rótulo (ISO), então a ordem lexical é cronológica.
    for version in VERSIONS:
        candidates = sorted((Path(model_dir) / "previsao").glob(f"{version}_*.joblib"))
        if candidates:
            return candidates[-1]
    return None


def product_predictor(model_dir: Path = settings.model_dir) -> Predictor:
    path = latest_model_path(model_dir)
    return DailyForecaster(DailyModel.load(path)) if path else SameSlotRecentBaseline()
