"""Rotina diária do produto: às 19h30 baixa a publicação do ONS; às 20h emite o aviso de amanhã.

Fluxo de uma emissão para o dia-alvo D (às 20h de D − 1, horário de Brasília):

1. baixa os arquivos mensais públicos do ONS que cobrem os 92 dias de histórico do modelo;
2. corta o histórico no que estava liberado às 20h de D − 1 (regra do calendário), recuando
   se o ONS ainda não publicou algum dia inteiro;
3. roda o modelo congelado e acrescenta o aviso de D a `data/processed/avisos.parquet`.

Não há banco de dados nem credenciais: a publicação do ONS é pública e a rotina é repetível.
Ao ligar, ela emite os dias que faltam no arquivo (até `LIMITE_RECUPERACAO`), então um
contêiner reiniciado se recompõe sozinho. A validação de setembro está encerrada, por isso
este caminho lê dados posteriores a `RESERVED_TEST_START`; nenhum modelo é retreinado.

Uso: `uv run python -m zelo.previsao.ao_vivo --uma-vez` (ou `--loop` no contêiner).
"""

import argparse
import io
import time as relogio
import traceback
import urllib.request
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl

from zelo.config import settings
from zelo.contracts import SOURCES, TIMEZONE
from zelo.forecasting import _RAW_COLUMNS
from zelo.previsao.avisos import ARCHIVE, entity_attributes
from zelo.previsao.calendario import EMISSION_TIME, Calendar, emission_cutoff, load_calendar
from zelo.previsao.modelo import DailyForecaster, DailyModel
from zelo.previsao.produto import HISTORY_DAYS, latest_model_path
from zelo.targets import derive_targets

URL = (
    "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/restricao_coff_{fonte}_tm/"
    "RESTRICAO_COFF_{FONTE}_{ano}_{mes:02d}.parquet"
)
BAIXA = time(19, 30)
LIMITE_RECUPERACAO = 7
CACHE = settings.data_dir / "interim" / "ons"
_ULTIMA_MEIA_HORA = time(23, 30)


def agora_brasilia() -> datetime:
    return datetime.now(ZoneInfo(TIMEZONE)).replace(tzinfo=None)


def url_publicacao(fonte: str, mes: date) -> str:
    return URL.format(fonte=fonte, FONTE=fonte.upper(), ano=mes.year, mes=mes.month)


def meses_necessarios(dia_alvo: date) -> list[date]:
    """Primeiros dias dos meses entre o início do histórico e a véspera do dia-alvo."""
    inicio = dia_alvo - timedelta(days=HISTORY_DAYS + 2)
    fim = dia_alvo - timedelta(days=1)
    meses, mes = [], inicio.replace(day=1)
    while mes <= fim:
        meses.append(mes)
        mes = (mes + timedelta(days=32)).replace(day=1)
    return meses


def baixar(meses: list[date], destino: Path = CACHE, hoje: date | None = None) -> list[Path]:
    """Baixa os arquivos mensais; meses fechados há mais de 1 mês ficam em cache."""
    hoje = hoje or agora_brasilia().date()
    recentes = {hoje.replace(day=1), (hoje.replace(day=1) - timedelta(days=1)).replace(day=1)}
    destino.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for fonte in SOURCES:
        for mes in meses:
            caminho = destino / f"{fonte}_{mes:%Y_%m}.parquet"
            if mes in recentes or not caminho.exists():
                with urllib.request.urlopen(url_publicacao(fonte, mes), timeout=120) as resposta:
                    conteudo = resposta.read()
                # Grava por arquivo temporário: uma falha no meio não corrompe o cache.
                temporario = caminho.with_suffix(".tmp")
                temporario.write_bytes(conteudo)
                temporario.replace(caminho)
            caminhos.append(caminho)
    return caminhos


def normalizar(frame: pl.DataFrame, fonte: str) -> pl.DataFrame:
    """Publicação atual do ONS nas colunas e tipos do snapshot."""
    return (
        frame.with_columns(pl.lit(fonte).alias("fonte"))
        .select(_RAW_COLUMNS)
        .with_columns(
            pl.col("din_instante").cast(pl.Datetime("us")),
            pl.col("val_geracaolimitada", "val_geracaoreferencia", "val_geracao").cast(
                pl.Float64, strict=False
            ),
            pl.col("cod_razaorestricao", "cod_origemrestricao").cast(pl.String),
        )
    )


def ler(caminhos: list[Path]) -> pl.DataFrame:
    frames = []
    for caminho in caminhos:
        fonte = caminho.name.split("_")[0]
        frames.append(normalizar(pl.read_parquet(io.BytesIO(caminho.read_bytes())), fonte))
    historia = pl.concat(frames).unique(["fonte", "id_ons", "din_instante"], keep="last")
    return derive_targets(historia.sort(["fonte", "id_ons", "din_instante"]))


def corte_efetivo(dia_alvo: date, historia: pl.DataFrame, calendar: Calendar) -> datetime:
    """Corte da emissão das 20h da véspera, limitado ao último dia inteiro publicado."""
    regra = emission_cutoff(dia_alvo, calendar)
    ultimo = historia["din_instante"].max()
    completo = ultimo.date() if ultimo.time() >= _ULTIMA_MEIA_HORA else ultimo.date() - timedelta(1)
    return min(regra, datetime.combine(completo + timedelta(days=1), time()))


def dias_pendentes(
    ultimo: date | None, agora: datetime, limite: int = LIMITE_RECUPERACAO
) -> list[date]:
    """Dias-alvo ainda sem aviso: até amanhã depois das 20h, senão até hoje."""
    alvo_final = agora.date() + timedelta(days=1 if agora.time() >= EMISSION_TIME else 0)
    inicio = max(
        ultimo + timedelta(days=1) if ultimo else alvo_final, alvo_final - timedelta(limite - 1)
    )
    return [inicio + timedelta(days=i) for i in range((alvo_final - inicio).days + 1)]


def proximo_horario(agora: datetime, hora: int, minuto: int) -> datetime:
    alvo = datetime.combine(agora.date(), time(hora, minuto))
    return alvo if alvo > agora else alvo + timedelta(days=1)


def anexar(caminho: Path, aviso: pl.DataFrame) -> None:
    """Grava o aviso substituindo o mesmo dia-alvo; escrita atômica."""
    if aviso.is_empty():
        raise ValueError("aviso vazio: nada a gravar")
    t0s = aviso["t0"].unique().implode()
    partes = [aviso]
    if caminho.exists():
        partes.insert(0, pl.read_parquet(caminho).filter(~pl.col("t0").is_in(t0s)))
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    pl.concat(partes, how="diagonal_relaxed").sort(["t0", "fonte", "id_ons"]).write_parquet(
        temporario
    )
    temporario.replace(caminho)


def emitir(
    dia: date, historia: pl.DataFrame, forecaster: DailyForecaster, calendar
) -> pl.DataFrame:
    corte = corte_efetivo(dia, historia, calendar)
    emitido = datetime.combine(dia - timedelta(days=1), EMISSION_TIME)
    aviso = forecaster.predict(
        historia,
        datetime.combine(dia, time()),
        corte,
        generated_at=agora_brasilia(),
        emitted_at=emitido,
        allow_reserved_test=True,
    )
    return aviso.join(entity_attributes(historia), on=["fonte", "id_ons"], how="left")


def rodar(agora: datetime | None = None, arquivo: Path = ARCHIVE) -> list[date]:
    """Baixa o ONS e emite todos os avisos pendentes. Devolve os dias emitidos."""
    agora = agora or agora_brasilia()
    ultimo = pl.read_parquet(arquivo, columns=["t0"])["t0"].max() if arquivo.exists() else None
    pendentes = dias_pendentes(ultimo.date() if ultimo else None, agora)
    if not pendentes:
        return []
    meses = sorted({m for dia in pendentes for m in meses_necessarios(dia)})
    historia = ler(baixar(meses, hoje=agora.date()))
    calendar = load_calendar()
    modelo = latest_model_path()
    if modelo is None:
        raise FileNotFoundError("nenhum modelo em models/previsao")
    forecaster = DailyForecaster(DailyModel.load(modelo), calendar)
    emitidos = []
    for dia in pendentes:
        aviso = emitir(dia, historia, forecaster, calendar)
        if aviso.is_empty():
            print(f"{dia}: sem histórico suficiente para emitir", flush=True)
            continue
        anexar(arquivo, aviso)
        emitidos.append(dia)
        print(f"{dia}: aviso emitido ({aviso.height} linhas)", flush=True)
    return emitidos


def _tentar(agora: datetime | None = None) -> None:
    try:
        rodar(agora)
    except Exception:  # noqa: BLE001 — a rotina não pode derrubar o contêiner
        traceback.print_exc()


def loop() -> None:
    """Recupera pendências ao ligar; depois baixa às 19h30 e emite às 20h, todo dia."""
    _tentar()
    while True:
        agora = agora_brasilia()
        baixa = proximo_horario(agora, BAIXA.hour, BAIXA.minute)
        relogio.sleep(max((baixa - agora).total_seconds(), 1))
        try:
            dia = agora_brasilia().date() + timedelta(days=1)
            baixar(meses_necessarios(dia))
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        agora = agora_brasilia()
        emissao = proximo_horario(agora, EMISSION_TIME.hour, EMISSION_TIME.minute)
        relogio.sleep(max((emissao - agora).total_seconds(), 1))
        _tentar()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--uma-vez", action="store_true")
    grupo.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    if args.loop:
        loop()
    else:
        print(rodar())


if __name__ == "__main__":
    main()
