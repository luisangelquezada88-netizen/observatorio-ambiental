"""Extractor meteorología Open-Meteo (ERA5 + forecast diario).
CLI: python -m src.extract.openmeteo_meteorologia --fecha YYYY-MM-DD [--out lake]
Idempotente: sobrescribe la partición fecha=YYYY-MM-DD.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

from src.config.puntos_monitoreo import PUNTOS
from src.extract._http import get_json

API_URL = "https://api.open-meteo.com/v1/forecast"
DAILY_VARS = (
    "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
    "precipitation_sum,rain_sum,snowfall_sum,"
    "wind_speed_10m_max,wind_gusts_10m_max,shortwave_radiation_sum,et0_fao_evapotranspiration"
)
CHUNK = 20  # Bloques chicos + pausa: evita 429 en IPs compartidas (D-09).
PAUSA_BLOQUES_SEG = 3
RETRIES = 4  # Compat: la reintentación real vive en src.extract._http.


def _fetch_chunk(lats: list[float], lons: list[float], fecha: str) -> list[dict]:
    params = {
        "latitude": ",".join(map(str, lats)),
        "longitude": ",".join(map(str, lons)),
        "daily": DAILY_VARS,
        "timezone": "auto",
        "start_date": fecha,
        "end_date": fecha,
    }
    data = get_json(API_URL, params, "meteorologia")
    return data if isinstance(data, list) else [data]


def extraer(fecha: str, out_root: str | Path = "lake") -> Path:
    out_root = Path(out_root)
    part = out_root / "raw" / "meteorologia" / f"fecha={fecha}"
    part.mkdir(parents=True, exist_ok=True)

    filas: list[dict] = []
    for i in range(0, len(PUNTOS), CHUNK):
        bloque = PUNTOS[i : i + CHUNK]
        lats = [p["lat"] for p in bloque]
        lons = [p["lon"] for p in bloque]
        resp = _fetch_chunk(lats, lons, fecha)
        for p, loc in zip(resp, bloque):
            daily = p.get("daily", {})
            for k in range(len(daily.get("time", []))):
                filas.append(
                    {
                        "punto_id": loc["id"],
                        "ciudad": loc["ciudad"],
                        "pais": loc["pais"],
                        "iso3": loc["iso3"],
                        "region": loc["region"],
                        "lat": loc["lat"],
                        "lon": loc["lon"],
                        "fecha": daily["time"][k],
                        "temp_max_c": daily.get("temperature_2m_max", [None])[k],
                        "temp_min_c": daily.get("temperature_2m_min", [None])[k],
                        "temp_media_c": (daily.get("temperature_2m_mean", [None])[k]),
                        "precipitacion_mm": daily.get("precipitation_sum", [None])[k],
                        "lluvia_mm": daily.get("rain_sum", [None])[k],
                        "viento_max_kmh": daily.get("wind_speed_10m_max", [None])[k],
                        "rafaga_max_kmh": daily.get("wind_gusts_10m_max", [None])[k],
                        "radiacion_mj_m2": daily.get("shortwave_radiation_sum", [None])[k],
                        "et0_mm": daily.get("et0_fao_evapotranspiration", [None])[k],
                    }
                )
        print(f"[meteorologia] bloque {i // CHUNK + 1}: {len(bloque)} puntos", flush=True)
        if i + CHUNK < len(PUNTOS):
            time.sleep(PAUSA_BLOQUES_SEG)  # Pacing anti-429 (D-09).

    df = pd.DataFrame(filas)
    destino = part / "meteorologia.parquet"
    # Sobrescribe (idempotencia): mismo fecha -> mismo archivo.
    df.to_parquet(destino, index=False)
    print(f"[meteorologia] {len(df)} filas -> {destino}", flush=True)
    return destino


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", required=True, help="YYYY-MM-DD")
    ap.add_argument("--out", default="lake")
    args = ap.parse_args(argv)
    extraer(args.fecha, args.out)


if __name__ == "__main__":
    sys.exit(main())
