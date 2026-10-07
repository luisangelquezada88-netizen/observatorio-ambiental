"""Extractor deforestación Global Forest Watch (pérdida anual de cobertura arbórea).
CLI: python -m src.extract.gfw_deforestacion --year 2023 [--out lake]
Estrategia MVP (ver docs/decisiones.md):
- Si hay GFW_API_KEY, intenta la Data API (dataset umd_tree_cover_loss).
- Si no hay key o falla, genera partición con esquema canónico vacío + flag,
  para no bloquear el MVP; el dashboard muestra fallback OWID forest-change.
Idempotente: sobrescribe fecha=year-12-31.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
import requests

ISO3_FOCO = [
    "BRA", "COL", "PER", "MEX", "ARG", "CHL", "ECU", "BOL", "PRY", "URY",
    "VEN", "GTM", "HND", "NIC", "CRI", "PAN", "CUB", "DOM", "HTI", "JAM",
    "IDN", "COD", "MYS", "USA", "CAN", "RUS", "CHN", "AUS", "IND", "ETH",
]
GFW_URL = "https://data-api.globalforestwatch.org/dataset/umd_tree_cover_loss/v2023/query"


def _intentar_gfw(api_key: str, year: int) -> pd.DataFrame | None:
    try:
        headers = {"x-api-key": api_key, "Content-Type": "application/json"}
        # Consulta agregada por país (adm0). Limitada al foco para el MVP.
        sql = (
            "SELECT country, umd_tree_cover_loss__year AS anio, "
            "SUM(umd_tree_cover_loss__ha) AS perdida_ha "
            f"FROM data WHERE umd_tree_cover_loss__year = {year} "
            "GROUP BY country, umd_tree_cover_loss__year LIMIT 100"
        )
        r = requests.post(GFW_URL, json={"sql": sql}, headers=headers, timeout=60)
        r.raise_for_status()
        payload = r.json()
        rows = payload.get("data", [])
        if not rows:
            return None
        return pd.DataFrame(rows)
    except Exception as e:  # noqa: BLE001
        print(f"[deforestacion] GFW API no disponible ({e}); usando fallback.", flush=True)
        return None


def extraer(year: int, out_root: str | Path = "lake") -> Path:
    out_root = Path(out_root)
    fecha_part = f"{year}-12-31"
    part = out_root / "raw" / "deforestacion" / f"fecha={fecha_part}"
    part.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("GFW_API_KEY", "").strip()
    df: pd.DataFrame | None = _intentar_gfw(api_key, year) if api_key else None

    if df is None or df.empty:
        # Fallback canónico: esquema estable, sin filas (dashboard usa OWID).
        df = pd.DataFrame(
            {"iso3": pd.Series(dtype="str"), "anio": pd.Series(dtype="int"),
             "perdida_ha": pd.Series(dtype="float"), "fuente": pd.Series(dtype="str")}
        )
        print("[deforestacion] partición vacía canónica (sin key GFW). Ver docs/decisiones.md D-03.", flush=True)
    else:
        df = df.rename(columns={"country": "iso3", "anio": "anio"})
        df["fuente"] = "GFW umd_tree_cover_loss v2023"
        df = df[df["iso3"].isin(ISO3_FOCO)] if "iso3" in df.columns else df

    destino = part / "deforestacion.parquet"
    df.to_parquet(destino, index=False)
    print(f"[deforestacion] {len(df)} filas año {year} -> {destino}", flush=True)
    return destino


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--out", default="lake")
    args = ap.parse_args(argv)
    extraer(args.year, args.out)


if __name__ == "__main__":
    sys.exit(main())
