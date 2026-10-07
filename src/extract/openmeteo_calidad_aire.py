"""Extractor calidad del aire Open-Meteo (CAMS/Copernicus, horario -> agregado diario).
CLI: python -m src.extract.openmeteo_calidad_aire --fecha YYYY-MM-DD
Idempotente: sobrescribe la partición.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

from src.config.puntos_monitoreo import PUNTOS
from src.extract._http import get_json

API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
HOURLY_VARS = "pm2_5,pm10,ozone,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide,us_aqi,european_aqi"
CHUNK = 20  # Bloques chicos + pausa: evita 429 en IPs compartidas (D-09).
PAUSA_BLOQUES_SEG = 3


def _fetch_chunk(lats: list[float], lons: list[float], fecha: str) -> list[dict]:
    params = {
        "latitude": ",".join(map(str, lats)),
        "longitude": ",".join(map(str, lons)),
        "hourly": HOURLY_VARS,
        "start_date": fecha,
        "end_date": fecha,
        "timezone": "auto",
    }
    data = get_json(API_URL, params, "calidad_aire")
    return data if isinstance(data, list) else [data]


def _agregar_diario(df_h: pd.DataFrame) -> pd.DataFrame:
    agg = {
        "pm2_5": ["mean", "max"],
        "pm10": ["mean", "max"],
        "ozone": ["mean", "max"],
        "nitrogen_dioxide": ["mean", "max"],
        "sulphur_dioxide": ["mean", "max"],
        "carbon_monoxide": ["mean", "max"],
        "us_aqi": ["mean", "max"],
        "european_aqi": ["mean", "max"],
    }
    g = df_h.groupby(
        ["punto_id", "ciudad", "pais", "iso3", "region", "lat", "lon", "fecha"], as_index=False
    ).agg(agg)
    g.columns = [
        "punto_id", "ciudad", "pais", "iso3", "region", "lat", "lon", "fecha",
        "pm25_media", "pm25_max", "pm10_media", "pm10_max",
        "o3_media", "o3_max", "no2_media", "no2_max",
        "so2_media", "so2_max", "co_media", "co_max",
        "us_aqi_media", "us_aqi_max", "eu_aqi_media", "eu_aqi_max",
    ]
    return g


def extraer(fecha: str, out_root: str | Path = "lake") -> Path:
    out_root = Path(out_root)
    part = out_root / "raw" / "calidad_aire" / f"fecha={fecha}"
    part.mkdir(parents=True, exist_ok=True)

    horas: list[dict] = []
    for i in range(0, len(PUNTOS), CHUNK):
        bloque = PUNTOS[i : i + CHUNK]
        resp = _fetch_chunk([p["lat"] for p in bloque], [p["lon"] for p in bloque], fecha)
        for p, loc in zip(resp, bloque):
            hourly = p.get("hourly", {})
            times = hourly.get("time", [])
            for k, ts in enumerate(times):
                horas.append(
                    {
                        "punto_id": loc["id"],
                        "ciudad": loc["ciudad"],
                        "pais": loc["pais"],
                        "iso3": loc["iso3"],
                        "region": loc["region"],
                        "lat": loc["lat"],
                        "lon": loc["lon"],
                        "fecha": ts[:10],
                        "pm2_5": (hourly.get("pm2_5") or [None] * len(times))[k],
                        "pm10": (hourly.get("pm10") or [None] * len(times))[k],
                        "ozone": (hourly.get("ozone") or [None] * len(times))[k],
                        "nitrogen_dioxide": (hourly.get("nitrogen_dioxide") or [None] * len(times))[k],
                        "sulphur_dioxide": (hourly.get("sulphur_dioxide") or [None] * len(times))[k],
                        "carbon_monoxide": (hourly.get("carbon_monoxide") or [None] * len(times))[k],
                        "us_aqi": (hourly.get("us_aqi") or [None] * len(times))[k],
                        "european_aqi": (hourly.get("european_aqi") or [None] * len(times))[k],
                    }
                )
        print(f"[calidad_aire] bloque {i // CHUNK + 1}: {len(bloque)} puntos", flush=True)
        if i + CHUNK < len(PUNTOS):
            time.sleep(PAUSA_BLOQUES_SEG)  # Pacing anti-429 (D-09).

    df_h = pd.DataFrame(horas)
    df = _agregar_diario(df_h) if not df_h.empty else pd.DataFrame()
    destino = part / "calidad_aire.parquet"
    df.to_parquet(destino, index=False)
    print(f"[calidad_aire] {len(df)} filas diarias -> {destino}", flush=True)
    return destino


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", required=True)
    ap.add_argument("--out", default="lake")
    args = ap.parse_args(argv)
    extraer(args.fecha, args.out)


if __name__ == "__main__":
    sys.exit(main())
