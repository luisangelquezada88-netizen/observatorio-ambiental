"""Extractor CO2 Our World in Data (CSV directo, sin key).
CLI: python -m src.extract.owid_co2 --year 2023 [--out lake]
Fuente: https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv
Filtra ISO3 foco LatAm + top emisores globales. Idempotente por fecha=year-12-31.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

OWID_URL = "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
ISO3_FOCO = [
    "MEX", "GTM", "HND", "SLV", "NIC", "CRI", "PAN", "CUB", "DOM", "HTI", "JAM",
    "COL", "VEN", "ECU", "PER", "BOL", "CHL", "ARG", "URY", "PRY", "BRA",
    "USA", "CHN", "IND", "RUS", "JPN", "DEU", "GBR", "FRA", "ESP", "CAN",
    "AUS", "IDN", "ZAF", "SAU", "IRN", "KOR", "ITA", "TUR", "EGY", "NGA",
]
COLS = ["country", "year", "iso_code", "co2", "co2_per_capita", "co2_per_gdp",
        "coal_co2", "oil_co2", "gas_co2", "cement_co2", "population", "gdp"]


def extraer(year: int, out_root: str | Path = "lake") -> Path:
    out_root = Path(out_root)
    part = out_root / "raw" / "co2" / f"fecha={year}-12-31"
    part.mkdir(parents=True, exist_ok=True)

    last_err: Exception | None = None
    df = None
    for intento in range(1, 5):
        try:
            df_all = pd.read_csv(OWID_URL, usecols=lambda c: c in COLS, low_memory=False)
            df = df_all[(df_all["year"] == year) & (df_all["iso_code"].isin(ISO3_FOCO))].copy()
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"[co2] intento {intento} falló: {e}", flush=True)
            time.sleep(2**intento)
    if df is None:
        raise RuntimeError(f"[co2] descarga OWID falló: {last_err}")
    df = df.rename(columns={"iso_code": "iso3", "year": "anio"})
    df["fuente"] = "OWID co2-data"
    destino = part / "co2.parquet"
    df.to_parquet(destino, index=False)
    print(f"[co2] {len(df)} filas año {year} -> {destino}", flush=True)
    return destino


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--out", default="lake")
    args = ap.parse_args(argv)
    extraer(args.year, args.out)


if __name__ == "__main__":
    sys.exit(main())
