from datetime import datetime, timedelta

from curtamap.audit import connect
from curtamap.eda import aggregate_table, concentration, episode_tables


def events(con, rows):
    con.execute(
        "CREATE TABLE t(fonte VARCHAR,id_ons VARCHAR,din_instante TIMESTAMP, "
        "corte_positivo BOOLEAN,energia_mwh DOUBLE)"
    )
    con.executemany("INSERT INTO t VALUES (?,?,?,?,?)", rows)


def test_episodes_break_at_gap_zero_unknown_source_and_entity():
    t = datetime(2025, 1, 1)
    with connect() as con:
        events(
            con,
            [
                ("eolica", "A", t, True, 1.0),
                ("eolica", "A", t + timedelta(minutes=30), True, 2.0),
                ("eolica", "A", t + timedelta(minutes=90), True, 3.0),
                ("eolica", "A", t + timedelta(minutes=120), False, 0.0),
                ("eolica", "A", t + timedelta(minutes=150), True, 4.0),
                ("eolica", "A", t + timedelta(minutes=180), None, None),
                ("eolica", "A", t + timedelta(minutes=210), True, 5.0),
                ("eolica", "B", t, True, 6.0),
                ("fotovoltaica", "A", t, True, 7.0),
            ],
        )
        summary, persistence = episode_tables(con)
    a = next(r for r in summary if r["fonte"] == "eolica" and r["id_ons"] == "A")
    assert a["episodes"] == 4
    assert a["max_slots"] == 2
    assert a["single_slot_episodes"] == 3
    p = next(r for r in persistence if r["id_ons"] == "A" and r["fonte"] == "eolica")
    assert p["positive_pairs"] == 2  # primeiro e segundo episódios têm sucessor conhecido
    assert p["positive_followed_positive"] == 1


def test_concentration_crossing_threshold_includes_crossing_entity():
    rows = [
        {"fonte": "eolica", "id_ons": x, "mwh": v} for x, v in [("A", 60), ("B", 25), ("C", 15)]
    ]
    result = concentration(rows)
    assert [r["entities"] for r in result] == [1, 2, 3]
    assert concentration([{"fonte": "eolica", "id_ons": "A", "mwh": 0}]) == []


def test_aggregate_does_not_turn_unknown_energy_into_zero():
    with connect() as con:
        con.execute("""CREATE TABLE t(fonte VARCHAR,restricao_registrada BOOLEAN,
            corte_positivo BOOLEAN,energia_mwh DOUBLE,energia_bruta_mwh DOUBLE,
            razao_desconhecida BOOLEAN,volume_valido BOOLEAN)""")
        con.execute("INSERT INTO t VALUES ('eolica',true,NULL,NULL,NULL,true,false)")
        r = aggregate_table(con, ["fonte"])[0]
        assert r["mwh"] is None
        assert r["invalid_volume"] == 1
        assert r["limited"] == 1
        assert r["rows"] == 1


def test_episode_duration_distribution_uses_same_breaks():
    from curtamap.eda import episode_durations

    t = datetime(2025, 1, 1)
    with connect() as con:
        events(
            con,
            [
                ("eolica", "A", t, True, 1.0),
                ("eolica", "A", t + timedelta(minutes=30), True, 1.0),
                ("eolica", "A", t + timedelta(minutes=90), True, 1.0),  # lacuna quebra
                ("eolica", "B", t + timedelta(minutes=120), True, 1.0),
                ("eolica", "B", t + timedelta(minutes=150), None, None),  # desconhecido quebra
                ("eolica", "B", t + timedelta(minutes=180), True, 1.0),
            ],
        )
        rows = episode_durations(con)
    assert rows == [
        {"fonte": "eolica", "slots": 1, "episodes": 3},
        {"fonte": "eolica", "slots": 2, "episodes": 1},
    ]


def test_same_time_previous_day_persistence_requires_observed_pair():
    from curtamap.eda import daily_persistence

    t = datetime(2025, 1, 1, 10)
    day = timedelta(days=1)
    with connect() as con:
        events(
            con,
            [
                ("eolica", "A", t, True, 1.0),
                ("eolica", "A", t + day, True, 1.0),
                ("eolica", "A", t + timedelta(minutes=30), True, 1.0),
                ("eolica", "A", t + day + timedelta(minutes=30), False, 0.0),
                ("eolica", "A", t + timedelta(hours=1), True, 1.0),  # dia seguinte ausente
                ("eolica", "A", t + timedelta(hours=2), None, None),
                ("eolica", "A", t + day + timedelta(hours=2), True, 1.0),  # anterior desconhecido
            ],
        )
        r = daily_persistence(con)[0]
    assert r["pairs"] == 2
    assert r["previous_positive"] == 2
    assert r["both_positive"] == 1
    assert r["current_positive"] == 1
