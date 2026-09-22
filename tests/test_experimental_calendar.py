from datetime import date
from pathlib import Path

from curtamap.experimental.calendar import load_calendar_manifest


def test_frozen_calendar_covers_2023_2026_and_hashes_manifest() -> None:
    path = Path("configs/experimental/calendar-2023-2026.json")
    loaded = load_calendar_manifest(path)
    assert loaded.calendar.version == "curtamap-conservador-2023-2026-v1"
    assert len(loaded.sha256) == 64
    assert set(loaded.years) == {2023, 2024, 2025, 2026}
    assert date(2025, 3, 5) in loaded.calendar.non_business_days  # parcial conta como inteiro
    assert date(2025, 4, 23) in loaded.calendar.non_business_days  # São Jorge/RJ
    assert date(2026, 4, 20) in loaded.calendar.non_business_days  # ponto facultativo federal
    assert loaded.sources
