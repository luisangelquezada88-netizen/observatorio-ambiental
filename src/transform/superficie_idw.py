"""Superficie IDW de PM2.5 sobre LatAm (versión avanzada, D-13).
CLI: python -m src.transform.superficie_idw --fecha YYYY-MM-DD [--lake lake]
Lee:  lake/serving/indicador_diario/fecha=FECHA/*.parquet
Escribe (sobrescribe = idempotente):
  lake/serving/superficies/fecha=FECHA/pm25.png   (raster bandas AQI)
  lake/serving/superficies/fecha=FECHA/meta.json  (rmse_loo, n, params)
Método: IDW p=2 sobre malla 0.5°, corte a 1300 km (más allá = NaN).
Límites honestos: ignora barreras (Andes) y no enmascara costa.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

LAT0, LAT1 = -56.0, 33.0
LON0, LON1 = -120.0, -30.0
RES = 0.5
P = 2.0
CORTE_KM = 1300.0
# Cortes = bandas AQI del dashboard (coherencia de color punto↔raster).
NIVELES = [0, 12, 35.4, 55.4, 150.4, 250.4, 600]
COLORES = ["#2d6a4f", "#ee9b00", "#ca6702", "#bb3e03", "#9d0208", "#6a040f"]


def _haversine_km(a_lat, a_lon, b_lat, b_lon) -> np.ndarray:
    """Distancia haversine (km) entre vectores (N,) y (M,) -> (N, M)."""
    r = 6371.0
    a_lat, a_lon = np.radians(a_lat)[:, None], np.radians(a_lon)[:, None]
    b_lat, b_lon = np.radians(b_lat)[None, :], np.radians(b_lon)[None, :]
    dlat, dlon = b_lat - a_lat, b_lon - a_lon
    h = np.sin(dlat / 2) ** 2 + np.cos(a_lat) * np.cos(b_lat) * np.sin(dlon / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(np.clip(h, 0, 1)))


def idw_grid(df: pd.DataFrame, res: float = RES, p: float = P,
             corte_km: float = CORTE_KM) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Devuelve (lats, lons, malla enmascarada) interpolada por IDW."""
    pts = df.dropna(subset=["pm25_media", "lat", "lon"]).copy()
    slat, slon = pts["lat"].to_numpy(), pts["lon"].to_numpy()
    sval = pts["pm25_media"].to_numpy(dtype=float)
    lats = np.arange(LAT0, LAT1 + res, res)
    lons = np.arange(LON0, LON1 + res, res)
    glon, glat = np.meshgrid(lons, lats)
    d = _haversine_km(glat.ravel(), glon.ravel(), slat, slon)
    dmin = d.min(axis=1)
    with np.errstate(divide="ignore"):
        w = 1.0 / np.power(np.maximum(d, 1e-6), p)
    exactas = dmin < 1e-3
    num = (w * sval[None, :]).sum(axis=1)
    den = w.sum(axis=1)
    malla = np.where(exactas, sval[d.argmin(axis=1)], num / np.maximum(den, 1e-12))
    malla = np.where(dmin > corte_km, np.nan, malla).reshape(glat.shape)
    return lats, lons, np.ma.masked_invalid(malla)


def loo_rmse(df: pd.DataFrame, p: float = P, corte_km: float = CORTE_KM) -> float:
    """RMSE leave-one-out: interpola cada estación sin ella misma."""
    pts = df.dropna(subset=["pm25_media", "lat", "lon"]).copy()
    slat, slon = pts["lat"].to_numpy(), pts["lon"].to_numpy()
    sval = pts["pm25_media"].to_numpy(dtype=float)
    n = len(pts)
    if n < 3:
        return float("nan")
    d = _haversine_km(slat, slon, slat, slon)
    np.fill_diagonal(d, np.inf)
    with np.errstate(divide="ignore"):
        w = 1.0 / np.power(d, p)
    w[d > corte_km] = 0.0
    den = w.sum(axis=1)
    pred = np.where(den > 0, (w * sval[None, :]).sum(axis=1) / np.maximum(den, 1e-12), np.nan)
    ok = ~np.isnan(pred)
    return float(np.sqrt(np.mean((pred[ok] - sval[ok]) ** 2))) if ok.any() else float("nan")


def generar(fecha: str, lake: str | Path = "lake") -> dict:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap

    lake = Path(lake)
    src = lake / "serving" / "indicador_diario" / f"fecha={fecha}"
    fich = sorted(src.glob("*.parquet"))
    if not fich:
        raise FileNotFoundError(f"sin serving diario para {fecha}")
    df = pd.concat([pd.read_parquet(f) for f in fich], ignore_index=True)

    lats, lons, malla = idw_grid(df)
    rmse = loo_rmse(df)

    dest = lake / "serving" / "superficies" / f"fecha={fecha}"
    dest.mkdir(parents=True, exist_ok=True)
    cmap = ListedColormap(COLORES)
    norm = BoundaryNorm(NIVELES, cmap.N)
    fig = plt.figure(figsize=((LON1 - LON0) / RES / 100, (LAT1 - LAT0) / RES / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.imshow(malla, extent=[LON0, LON1, LAT0, LAT1], origin="lower",
              cmap=cmap, norm=norm, alpha=0.72, interpolation="bilinear")
    fig.savefig(dest / "pm25.png", transparent=True, bbox_inches="tight", pad_inches=0)
    plt.close(fig)

    meta = {"fecha": fecha, "n_puntos": int(df["pm25_media"].notna().sum()),
            "res_grados": RES, "p": P, "corte_km": CORTE_KM, "niveles_aqi": NIVELES,
            "rmse_loo_ugm3": None if np.isnan(rmse) else round(rmse, 2),
            "pm25_min": round(float(np.nanmin(malla)), 1),
            "pm25_max": round(float(np.nanmax(malla)), 1)}
    (dest / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"[idw] {fecha}: n={meta['n_puntos']} rmse_loo={meta['rmse_loo_ugm3']} -> {dest}", flush=True)
    return meta


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", required=True)
    ap.add_argument("--lake", default="lake")
    args = ap.parse_args(argv)
    generar(args.fecha, args.lake)


if __name__ == "__main__":
    sys.exit(main())
