"""Tests de la superficie IDW (sintéticos, sin red)."""
import json

import numpy as np
import pandas as pd


def _fake(n=12, seed=3):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "punto_id": [f"p{i}" for i in range(n)],
        "ciudad": [f"C{i}" for i in range(n)],
        "pais": ["T"] * n, "iso3": ["TST"] * n, "region": ["LatAm"] * n,
        "lat": rng.uniform(-30, 10, n), "lon": rng.uniform(-70, -40, n),
        "fecha": ["2025-01-15"] * n,
        "pm25_media": rng.uniform(5, 60, n),
    })


def test_idw_forma_y_decaimiento(tmp_path):
    from src.transform.superficie_idw import LAT0, LAT1, LON0, LON1, RES, idw_grid

    df = pd.DataFrame({
        "punto_id": ["a", "b"], "ciudad": ["A", "B"], "pais": ["T", "T"],
        "iso3": ["TST", "TST"], "region": ["LatAm"] * 2,
        "lat": [-10.0, -10.0], "lon": [-60.0, -40.0], "fecha": ["2025-01-15"] * 2,
        "pm25_media": [10.0, 50.0],
    })
    lats, lons, m, _dmin = idw_grid(df)
    assert lats[0] == LAT0 and lats[-1] <= LAT1 + RES and lons[0] == LON0 and lons[-1] <= LON1 + RES
    assert m.shape == (len(lats), len(lons))
    assert m.count() > 0  # hay celdas válidas dentro del corte
    # Cerca de A domina A; cerca de B domina B.
    ia = (np.abs(lats - -10.0)).argmin(), (np.abs(lons - -59.0)).argmin()
    ib = (np.abs(lats - -10.0)).argmin(), (np.abs(lons - -41.0)).argmin()
    assert m[ia] < m[ib]


def test_loo_rmse_sano():
    from src.transform.superficie_idw import loo_rmse

    rmse = loo_rmse(_fake())
    assert rmse >= 0 and rmse < 100


def test_generar_idempotente(tmp_path):
    from src.transform.superficie_idw import generar

    lake = tmp_path / "lake"
    d = lake / "serving" / "indicador_diario" / "fecha=2025-01-15"
    d.mkdir(parents=True, exist_ok=True)
    _fake().to_parquet(d / "indicador_diario.parquet", index=False)
    m1 = generar("2025-01-15", lake)
    m2 = generar("2025-01-15", lake)
    assert m1 == m2
    dest = lake / "serving" / "superficies" / "fecha=2025-01-15"
    assert (dest / "pm25.png").stat().st_size > 1000
    assert json.loads((dest / "meta.json").read_text())["n_puntos"] == 12
