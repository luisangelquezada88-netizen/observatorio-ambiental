"""Smoke end-to-end 1 día (H0/H1): extractores con mock + transform idempotente."""
from pathlib import Path

import pandas as pd


def _fake_raw(lake: Path, fecha: str):
    import numpy as np

    rng = np.random.default_rng(7)
    n = 10
    base = pd.DataFrame({
        "punto_id": [f"p{i}" for i in range(n)],
        "ciudad": [f"C{i}" for i in range(n)],
        "pais": ["Testlandia"] * n,
        "iso3": ["TST"] * n,
        "region": ["LatAm"] * 6 + ["Mundo"] * 4,
        "lat": rng.uniform(-30, 10, n),
        "lon": rng.uniform(-80, -40, n),
        "fecha": [fecha] * n,
    })
    met = base.assign(temp_max_c=28.0, temp_min_c=18.0, temp_media_c=23.0,
                      precipitacion_mm=2.0, viento_max_kmh=15.0, rafaga_max_kmh=25.0)
    aire = base.assign(pm25_media=10.0, pm25_max=20.0, pm10_media=18.0, o3_media=60.0,
                       no2_media=12.0, us_aqi_media=35.0, us_aqi_max=55.0)
    hidro = base.assign(caudal_m3s=120.0, caudal_medio_m3s=110.0, caudal_max_m3s=150.0)
    for nombre, df in (("meteorologia", met), ("calidad_aire", aire), ("hidrologia", hidro)):
        d = lake / "raw" / nombre / f"fecha={fecha}"
        d.mkdir(parents=True, exist_ok=True)
        df.to_parquet(d / f"{nombre}.parquet", index=False)


def test_transform_idempotente(tmp_path):
    from src.transform.indicadores import transformar

    lake = tmp_path / "lake"
    fecha = "2025-01-15"
    _fake_raw(lake, fecha)
    s1 = transformar(fecha, lake)
    import pyarrow.parquet as pq

    n1 = pq.read_table(s1["indicador_diario"]).num_rows
    s2 = transformar(fecha, lake)  # segunda corrida misma fecha
    n2 = pq.read_table(s2["indicador_diario"]).num_rows
    assert n1 == n2 == 10, f"idempotencia rota: {n1} vs {n2}"
    pais = pq.read_table(s2["indicador_pais"]).to_pandas()
    assert (pais["n_puntos"].sum()) == 10


def test_puntos_150():
    from src.config.puntos_monitoreo import PUNTOS, resumen

    r = resumen()
    assert r["total"] >= 140, f"se esperan ~150 puntos, hay {r['total']}"
    assert r["latam"] / r["total"] >= 0.55, "foco LatAm >=55%"
    ids = [p["id"] for p in PUNTOS]
    assert len(ids) == len(set(ids)), "ids duplicados"
    for p in PUNTOS:
        assert -90 <= p["lat"] <= 90 and -180 <= p["lon"] <= 180


def test_cli_extractores_compilan():
    import py_compile

    for m in ["src/extract/openmeteo_meteorologia.py", "src/extract/openmeteo_calidad_aire.py",
              "src/extract/openmeteo_hidrologia.py", "src/extract/gfw_deforestacion.py",
              "src/extract/owid_co2.py", "src/transform/indicadores.py", "src/load/postgis.py"]:
        py_compile.compile(m, doraise=True)
