"""Extractor hidrología Open-Meteo Flood API (GloFAS, caudal diario).
CLI: python -m src.extract.openmeteo_hidrologia --fecha YYYY-MM-DD
Nota: GloFAS es malla gruesa (~10 km); valores en cuencas pequeñas son
aproximados. Se documenta en docs/decisiones.md.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

from src.config.puntos_monitoreo import PUNTOS
from src.extract._http import get_json

API_URL = "https://flood-api.open-meteo.com/v1/flood"
# La Flood API solo expone river_discharge (sin variantes mean/median/max/min).
DAILY_VARS = "river_discharge"
CHUNK = 20  # Bloques chicos + pausa: evita 429 en IPs compartidas (D-09).
PAUSA_BLOQUES_SEG = 3


def _fetch_chunk(lats: list[float], lons: list[float], fecha: str) -> list[dict]:
    params = {
        "latitude": ",".join(map(str, lats)),
        "longitude": ",".join(map(str, lons)),
        "daily": DAILY_VARS,
        "start_date": fecha,
        "end_date": fecha,
        "timezone": "auto",
    }
    data = get_json(API_URL, params, "hidrologia")
    return data if isinstance(data, list) else [data]


def extraer(fecha: str, out_root: str | Path = "lake") -> Path:
    out_root = Path(out_root)
    part = out_root / "raw" / "hidrologia" / f"fecha={fecha}"
    part.mkdir(parents=True, exist_ok=True)

    filas: list[dict] = []
    for i in range(0, len(PUNTOS), CHUNK):
        bloque = PUNTOS[i : i + CHUNK]
        resp = _fetch_chunk([p["lat"] for p in bloque], [p["lon"] for p in bloque], fecha)
        for p, loc in zip(resp, bloque):
            daily = p.get("daily", {})
            for k in range(len(daily.get("time", []))):
                q = (daily.get("river_discharge") or [None] * len(daily.get("time", [])))[k]
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
                        "caudal_m3s": q,
                        "caudal_medio_m3s": q,
                        "caudal_mediana_m3s": q,
                        "caudal_max_m3s": q,
                        "caudal_min_m3s": q,
                        "es_cuenca": loc["tipo"] == "cuenca",
                    }
                )
        print(f"[hidrologia] bloque {i // CHUNK + 1}: {len(bloque)} puntos", flush=True)
        if i + CHUNK < len(PUNTOS):
            time.sleep(PAUSA_BLOQUES_SEG)  # Pacing anti-429 (D-09).

    df = pd.DataFrame(filas)
    destino = part / "hidrologia.parquet"
    df.to_parquet(destino, index=False)
    print(f"[hidrologia] {len(df)} filas -> {destino}", flush=True)
    return destino


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", required=True)
    ap.add_argument("--out", default="lake")
    args = ap.parse_args(argv)
    extraer(args.fecha, args.out)


if __name__ == "__main__":
    sys.exit(main())
