from curtamap.experimental.resources import peak_rss_bytes


def test_peak_rss_is_reported_in_bytes_on_every_platform() -> None:
    peak = peak_rss_bytes()
    assert isinstance(peak, int)
    # Um interpretador Python com Polars carregado ocupa dezenas de MiB; um valor abaixo
    # de 1 MiB indicaria unidade errada (KiB no Linux) em vez de bytes.
    assert peak > 1024**2


def test_peak_rss_never_decreases() -> None:
    first = peak_rss_bytes()
    buffer = bytearray(32 * 1024**2)
    second = peak_rss_bytes()
    del buffer
    assert second >= first
