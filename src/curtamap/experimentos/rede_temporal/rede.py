"""Rede temporal pequena: GRU sobre dias, com saída direta das 48 meias-horas do dia-alvo.

**Por que GRU e não TCN.** A emissão é diária e a entrada natural é uma sequência curta de
dias (28 passos, cada um com o vetor das 48 meias-horas). Com 28 passos, a TCN não traz
vantagem de campo receptivo nem de paralelismo, e a GRU de uma camada tem menos escolhas de
arquitetura (dilatações, kernel) e roda bem em CPU.

**Entrada de cada amostra (usina, dia-alvo T), só com dados até o último dia liberado L:**

- sequência dos `window_days` dias que terminam em L. Cada dia tem, por meia-hora:
  corte, volume / escala da usina, máscara de observação, fração cortada no estado (mesma
  fonte) e máscara do estado; mais o dia da semana e a posição relativa na janela;
- escala da usina = média da geração de referência nos dias observados da própria janela
  (piso de 1 MW). É calculada por amostra, só com o passado: não há estatística ajustada
  entre amostras e, portanto, nada a vazar entre divisões;
- estáticos: embedding da usina (0 = desconhecida), embedding da fonte, calendário de T
  (dia da semana, feriado nacional) e idade T − L.

**Ausência:** meia-hora sem observação entra como 0 **com máscara 0**, e o rótulo ausente é
mascarado na perda. A ausência nunca é tratada como corte zero observado.

**Saídas e perdas:** 48 logits de ocorrência (BCE) e 48 log-taxas de volume normalizado
(NLL de Poisson com entrada em log). A Poisson estima diretamente a média, o que absorve os
muitos zeros sem separar "probabilidade × volume condicional", produto que explodiu na
Etapa 2 anterior. Volume previsto = exp(log-taxa) × escala, em MWmed, sempre ≥ 0.

**Modelo compartilhado** entre as duas fontes e todas as usinas, com embeddings de fonte e de
usina. A justificativa é que o corte ENE atinge eólica e solar do mesmo estado ao mesmo
tempo, então há informação comum a aproveitar. Durante o treino, 10% das usinas viram
"desconhecida", para que usinas novas tenham uma representação treinada.
"""

import math
import time
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import polars as pl
import torch
from torch import nn

SLOTS = 48
_SOURCES = {"eolica": 0, "fotovoltaica": 1}
_PLANT = ["fonte", "id_ons"]


@dataclass(frozen=True)
class NetConfig:
    window_days: int = 28
    hidden: int = 64
    plant_dim: int = 8
    dropout: float = 0.1
    volume_weight: float = 1.0
    learning_rate: float = 2e-3
    batch_size: int = 512
    max_epochs: int = 12
    patience: int = 2
    unknown_plant_rate: float = 0.1
    train_days: int = 365
    validation_days: int = 28
    validation_gap_days: int = 7

    @property
    def input_size(self) -> int:
        return SLOTS * 5 + 7 + 1

    @property
    def calendar_size(self) -> int:
        return 7 + 1 + 1


@dataclass
class DailyTensor:
    """Arrays densos usina × dia × meia-hora, com máscara de observação."""

    plants: list[tuple[str, str]]
    plant_index: dict[tuple[str, str], int]
    plant_source: np.ndarray
    first_day: date
    day_index: dict[date, int]
    corte: np.ndarray
    volume: np.ndarray
    mask: np.ndarray
    reference: np.ndarray
    state_share: np.ndarray
    state_mask: np.ndarray

    @property
    def reference_filled(self) -> np.ndarray:
        if getattr(self, "_reference_filled", None) is None:
            self._reference_filled = np.nan_to_num(self.reference, nan=0.0)
        return self._reference_filled

    @staticmethod
    def from_base(base: pl.DataFrame) -> "DailyTensor":
        plants_frame = (
            base.sort("dia").group_by(_PLANT).agg(pl.col("id_estado").last()).sort(_PLANT)
        )
        plants = list(zip(plants_frame["fonte"], plants_frame["id_ons"], strict=True))
        plant_index = {plant: i for i, plant in enumerate(plants)}
        first, last = base["dia"].min(), base["dia"].max()
        n_days = (last - first).days + 1
        day_index = {first + timedelta(days=k): k for k in range(n_days)}
        shape = (len(plants), n_days, SLOTS)
        corte, volume, mask = (np.zeros(shape, np.float32) for _ in range(3))

        indexed = plants_frame.select(_PLANT).with_row_index("_p")
        rows = base.join(indexed, on=_PLANT).select(
            "_p",
            (pl.col("dia") - pl.lit(first)).dt.total_days().alias("_d"),
            "slot",
            "corte",
            "volume",
        )
        p = rows["_p"].to_numpy().astype(np.int64)
        d = rows["_d"].to_numpy()
        s = rows["slot"].to_numpy().astype(int)
        corte[p, d, s] = rows["corte"].to_numpy()
        volume[p, d, s] = rows["volume"].to_numpy()
        mask[p, d, s] = 1.0

        reference = np.full((len(plants), n_days), np.nan, np.float32)
        daily = (
            base.group_by([*_PLANT, "dia"])
            .agg(pl.col("referencia").mean())
            .join(indexed, on=_PLANT)
        )
        dd = daily.select((pl.col("dia") - pl.lit(first)).dt.total_days()).to_series().to_numpy()
        reference[daily["_p"].to_numpy().astype(np.int64), dd] = daily["referencia"].to_numpy()

        # Fração cortada por fonte × estado × dia × meia-hora, atribuída a cada usina pelo
        # seu estado mais recente.
        groups = sorted(set(zip(plants_frame["fonte"], plants_frame["id_estado"], strict=True)))
        group_index = {g: i for i, g in enumerate(groups)}
        plant_group = np.array(
            [
                group_index[(f, e)]
                for f, e in zip(plants_frame["fonte"], plants_frame["id_estado"], strict=True)
            ]
        )
        totals = np.zeros((len(groups), n_days, SLOTS), np.float32)
        counts = np.zeros_like(totals)
        np.add.at(totals, (plant_group[p], d, s), rows["corte"].to_numpy())
        np.add.at(counts, (plant_group[p], d, s), 1.0)
        share = np.divide(totals, counts, out=np.zeros_like(totals), where=counts > 0)
        return DailyTensor(
            plants=plants,
            plant_index=plant_index,
            plant_source=np.array([_SOURCES[f] for f, _ in plants]),
            first_day=first,
            day_index=day_index,
            corte=corte,
            volume=volume,
            mask=mask,
            reference=reference,
            state_share=share[plant_group],
            state_mask=(counts > 0).astype(np.float32)[plant_group],
        )

    def day(self, value: date) -> int:
        return (value - self.first_day).days


def _keys(frame: pl.DataFrame) -> list[tuple[str, str]]:
    return list(zip(frame["fonte"], frame["id_ons"], strict=True))


def samples_for_days(
    tensor: DailyTensor, mapping: pl.DataFrame, *, require_labels: bool
) -> pl.DataFrame:
    """Usina × dia-alvo do `mapping` (release_map); com `require_labels`, só T com rótulo."""
    plants = pl.DataFrame(tensor.plants, schema=_PLANT, orient="row")
    samples = plants.join(mapping, how="cross")
    if not require_labels:
        return samples
    p = np.array([tensor.plant_index[k] for k in _keys(samples)])
    d = np.array([tensor.day(x) for x in samples["dia"].to_list()])
    inside = (d >= 0) & (d < tensor.mask.shape[1])
    labelled = np.zeros(len(p), bool)
    labelled[inside] = tensor.mask[p[inside], d[inside]].any(axis=1)
    return samples.filter(pl.Series(labelled))


def _take(array: np.ndarray, p: np.ndarray, days: np.ndarray) -> np.ndarray:
    """array[p, days] com zeros fora do intervalo do tensor."""
    valid = (days >= 0) & (days < array.shape[1])
    out = array[p[:, None], np.clip(days, 0, array.shape[1] - 1)]
    return np.where(valid[..., None] if out.ndim == 3 else valid, out, 0)


def index_samples(
    tensor: DailyTensor,
    samples: pl.DataFrame,
    vocabulary: dict[tuple[str, str], int] | None = None,
) -> dict[str, np.ndarray]:
    """Índices inteiros de cada amostra; as entradas são montadas por lote (memória)."""
    vocabulary = vocabulary or {}
    keys = _keys(samples)
    calendar = np.concatenate(
        [
            np.eye(7, dtype=np.float32)[samples["dia_semana"].to_numpy().astype(int)],
            samples["feriado"].to_numpy().astype(np.float32)[:, None],
            (samples["idade"].to_numpy().astype(np.float32) / 7.0)[:, None],
        ],
        axis=1,
    )
    return {
        "p": np.array([tensor.plant_index[x] for x in keys], np.int64),
        "last": np.array([tensor.day(x) for x in samples["ultimo_dia"].to_list()], np.int64),
        "target": np.array([tensor.day(x) for x in samples["dia"].to_list()], np.int64),
        "plant": np.array([vocabulary.get(x, 0) for x in keys], np.int64),
        "calendar": calendar,
    }


def inputs_from_index(
    tensor: DailyTensor, index: dict[str, np.ndarray], config: NetConfig
) -> dict[str, np.ndarray]:
    k = config.window_days
    p, target = index["p"], index["target"]
    days = index["last"][:, None] - np.arange(k - 1, -1, -1)[None, :]

    mask = _take(tensor.mask, p, days)
    reference = _take(tensor.reference_filled, p, days)
    observed = mask.any(axis=2)
    total = (reference * observed).sum(axis=1)
    count = observed.sum(axis=1)
    scale = np.maximum(np.divide(total, count, out=np.ones_like(total), where=count > 0), 1.0)
    weekday = (tensor.first_day.weekday() + days) % 7
    sequence = np.concatenate(
        [
            _take(tensor.corte, p, days) * mask,
            _take(tensor.volume, p, days) / scale[:, None, None] * mask,
            mask,
            _take(tensor.state_share, p, days),
            _take(tensor.state_mask, p, days),
            np.eye(7, dtype=np.float32)[weekday],
            np.broadcast_to(np.linspace(-1, 0, k, dtype=np.float32), days.shape)[..., None],
        ],
        axis=2,
    ).astype(np.float32)
    target_mask = _take(tensor.mask, p, target[:, None])[:, 0]
    return {
        "sequence": sequence,
        "plant": index["plant"],
        "source": tensor.plant_source[p].astype(np.int64),
        "calendar": index["calendar"],
        "scale": scale.astype(np.float32),
        "y_cut": _take(tensor.corte, p, target[:, None])[:, 0] * target_mask,
        "y_volume": _take(tensor.volume, p, target[:, None])[:, 0] / scale[:, None] * target_mask,
        "y_mask": target_mask,
    }


def batch_inputs(
    tensor: DailyTensor,
    samples: pl.DataFrame,
    config: NetConfig,
    vocabulary: dict[tuple[str, str], int] | None = None,
) -> dict[str, np.ndarray]:
    return inputs_from_index(tensor, index_samples(tensor, samples, vocabulary), config)


def _subset(index: dict[str, np.ndarray], rows: np.ndarray) -> dict[str, np.ndarray]:
    return {k: v[rows] for k, v in index.items()}


def _batch(tensor, index, rows, config) -> dict[str, torch.Tensor]:
    inputs = inputs_from_index(tensor, _subset(index, rows), config)
    return {k: torch.from_numpy(np.ascontiguousarray(v)) for k, v in inputs.items()}


class GRUForecaster(nn.Module):
    def __init__(self, config: NetConfig, n_plants: int):
        super().__init__()
        self.project = nn.Linear(config.input_size, config.hidden)
        self.gru = nn.GRU(config.hidden, config.hidden, batch_first=True)
        self.plant = nn.Embedding(n_plants, config.plant_dim)
        self.source = nn.Embedding(len(_SOURCES), 4)
        width = config.hidden + config.plant_dim + 4 + config.calendar_size
        self.head = nn.Sequential(
            nn.Linear(width, 128),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(128, 2 * SLOTS),
        )

    def forward(self, batch: dict[str, torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor]:
        _, hidden = self.gru(torch.relu(self.project(batch["sequence"])))
        features = torch.cat(
            [
                hidden[-1],
                self.plant(batch["plant"]),
                self.source(batch["source"]),
                batch["calendar"],
            ],
            dim=1,
        )
        out = self.head(features)
        return out[:, :SLOTS], out[:, SLOTS:].clamp(-15.0, 6.0)


def masked_loss(logits, log_rate, y_cut, y_volume, mask, *, volume_weight: float):
    """BCE + peso × NLL de Poisson, só nas meias-horas com rótulo."""
    denominator = mask.sum().clamp(min=1.0)
    bce = nn.functional.binary_cross_entropy_with_logits(logits, y_cut, reduction="none")
    poisson = torch.exp(log_rate) - y_volume * log_rate
    return ((bce + volume_weight * poisson) * mask).sum() / denominator


def _loss(batch, logits, log_rate, config):
    return masked_loss(
        logits,
        log_rate,
        batch["y_cut"],
        batch["y_volume"],
        batch["y_mask"],
        volume_weight=config.volume_weight,
    )


def _epoch_loss(model, tensor, index, config) -> float:
    model.eval()
    total, weight = 0.0, 0.0
    n = len(index["p"])
    with torch.no_grad():
        for start in range(0, n, 2048):
            batch = _batch(tensor, index, np.arange(start, min(start + 2048, n)), config)
            logits, log_rate = model(batch)
            m = batch["y_mask"].sum().item()
            total += _loss(batch, logits, log_rate, config).item() * m
            weight += m
    return total / max(weight, 1.0)


def _train(model, tensor, index, config, epochs, rng, validation=None) -> list[dict]:
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=1e-4)
    history = []
    best, best_state, stale = math.inf, None, 0
    n = len(index["p"])
    for epoch in range(epochs):
        model.train()
        started = time.time()
        order = rng.permutation(n)
        for start in range(0, n, config.batch_size):
            batch = _batch(tensor, index, order[start : start + config.batch_size], config)
            unknown = torch.rand(len(batch["plant"])) < config.unknown_plant_rate
            batch["plant"] = torch.where(unknown, torch.zeros_like(batch["plant"]), batch["plant"])
            logits, log_rate = model(batch)
            loss = _loss(batch, logits, log_rate, config)
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        record = {"epoca": epoch + 1, "segundos": round(time.time() - started, 1)}
        if validation is not None:
            record["perda_validacao"] = _epoch_loss(model, tensor, validation, config)
            if record["perda_validacao"] < best - 1e-5:
                best, stale = record["perda_validacao"], 0
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            else:
                stale += 1
        history.append(record)
        if validation is not None and stale >= config.patience:
            break
    if best_state is not None:
        model.load_state_dict(best_state)
    return history


@dataclass
class FittedNet:
    model: GRUForecaster
    vocabulary: dict[tuple[str, str], int]
    config: NetConfig
    history: list[dict]
    best_epochs: int


def fit_net(
    tensor: DailyTensor,
    mapping: pl.DataFrame,
    cutoff: date,
    config: NetConfig,
    seed: int,
) -> FittedNet:
    """Parada antecipada numa validação interna recente, depois reajuste em toda a janela.

    Validação: dias-alvo nos últimos `validation_days` até o corte; ajuste da parada: dias-alvo
    até `validation_gap_days` antes do início da validação. Todos os rótulos usados são de
    dias ≤ `cutoff`. O modelo final é reajustado do zero, com a mesma semente, em toda a
    janela de treino e pelo número de épocas escolhido.
    """
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    window = mapping.filter(
        pl.col("dia") <= cutoff, pl.col("dia") > cutoff - timedelta(days=config.train_days)
    )
    samples = samples_for_days(tensor, window, require_labels=True)
    vocabulary = {plant: i + 1 for i, plant in enumerate(sorted(set(_keys(samples))))}
    validation_start = cutoff - timedelta(days=config.validation_days)
    early = samples.filter(
        pl.col("dia") <= validation_start - timedelta(days=config.validation_gap_days)
    )
    held = samples.filter(pl.col("dia") > validation_start)
    model = GRUForecaster(config, len(vocabulary) + 1)
    history = _train(
        model,
        tensor,
        index_samples(tensor, early, vocabulary),
        config,
        config.max_epochs,
        rng,
        validation=index_samples(tensor, held, vocabulary),
    )
    best_epochs = int(min(history, key=lambda r: r.get("perda_validacao", math.inf))["epoca"])
    torch.manual_seed(seed)
    final = GRUForecaster(config, len(vocabulary) + 1)
    refit = _train(
        final,
        tensor,
        index_samples(tensor, samples, vocabulary),
        config,
        best_epochs,
        np.random.default_rng(seed),
    )
    history += [{**r, "fase": "reajuste"} for r in refit]
    return FittedNet(final, vocabulary, config, history, best_epochs)


def predict_net(net: FittedNet, tensor: DailyTensor, samples: pl.DataFrame) -> pl.DataFrame:
    """Uma linha por amostra × meia-hora: `p` (probabilidade) e `v` (MWmed, ≥ 0)."""
    index = index_samples(tensor, samples, net.vocabulary)
    n = len(index["p"])
    net.model.eval()
    probabilities, volumes = [], []
    with torch.no_grad():
        for start in range(0, n, 2048):
            batch = _batch(tensor, index, np.arange(start, min(start + 2048, n)), net.config)
            logits, log_rate = net.model(batch)
            probabilities.append(torch.sigmoid(logits).numpy())
            volumes.append(torch.exp(log_rate).numpy() * batch["scale"].numpy()[:, None])
    p = np.concatenate(probabilities)
    v = np.concatenate(volumes)
    return (
        samples.select(_PLANT + ["dia"])
        .with_columns(
            pl.Series("p", list(p), dtype=pl.List(pl.Float64)),
            pl.Series("v", list(v), dtype=pl.List(pl.Float64)),
            pl.lit(list(range(SLOTS)), dtype=pl.List(pl.Int8)).alias("slot"),
        )
        .explode(["p", "v", "slot"])
    )
