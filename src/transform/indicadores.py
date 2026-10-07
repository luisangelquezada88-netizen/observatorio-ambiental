"""Transformación bronce → plata → oro con DuckDB (sin estado externo salvo lake/).
CLI: python -m src.transform.indicadores --fecha YYYY-MM-DD [--lake lake]
Lee:  lake/raw/{meteorologia,calidad_aire,hidrologia}/fecha=FECHA/*.parquet
Escribe (sobrescribe = idempotente):
  lake/curated/<fuente>/fecha=FECHA/*.parquet   (plata: validada)
  lake/serving/indicador_diario/fecha=FECHA/*.parquet  (oro: join 3 pilares)
  lake/serving/indicador_pais/fecha=FECHA/*.parquet    (oro agregado país)
Validaciones: nulos, rangos físicos, unidades. Anomalías -> docs/decisiones.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import duckdb  # type: ignore
    _HAY_DUCKDB = True
except Exception:  # noqa: BLE001 - Windows Store Python bloquea la DLL; fallback pandas
    duckdb = None  # type: ignore
    _HAY_DUCKDB = False

import pandas as pd
import pyarrow.parquet as pq

RANGOS = {
    "temp_max_c": (-60, 55),
    "temp_min_c": (-60, 55),
    "temp_media_c": (-60, 55),
    "precipitacion_mm": (0, 1000),
    "viento_max_kmh": (0, 350),
    "pm25_media": (0, 1000),
    "pm10_media": (0, 2000),
    "o3_media": (0, 800),
    "no2_media": (0, 2000),
    "caudal_m3s": (0, 300000),
}


def _leer(con, patron: str, etiqueta: str):
    try:
        if con is not None:
            df = con.execute(f"SELECT * FROM read_parquet('{patron}')").fetch_df()
        else:
            import glob as _glob

            fich = _glob.glob(patron)
            if not fich:
                raise FileNotFoundError(patron)
            df = pd.concat([pd.read_parquet(f) for f in fich], ignore_index=True)
        print(f"[transform] raw {etiqueta}: {len(df)} filas", flush=True)
        return df
    except Exception as e:  # noqa: BLE001
        print(f"[transform] sin {etiqueta} ({patron}): {e}", flush=True)
        return None


def _categoria_pm25(v):
    """Bandas EPA (AQI EE. UU. para PM2.5 24h), NO categorías OMS.

    La OMS 2021 solo fija guía 24h (15 µg/m³) + objetivos intermedios
    (25/37.5/50/75). Estas bandas son los breakpoints del AQI y se
    etiquetan como tales en el dashboard (D-11).
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if v <= 12:
        return "Buena"
    if v <= 35.4:
        return "Moderada"
    if v <= 55.4:
        return "Dañina (sensible)"
    if v <= 150.4:
        return "Dañina"
    if v <= 250.4:
        return "Muy dañina"
    return "Peligrosa"


def transformar(fecha: str, lake: str | Path = "lake") -> dict:
    lake = Path(lake)
    raw = lake / "raw"
    con = duckdb.connect() if _HAY_DUCKDB else None
    if not _HAY_DUCKDB:
        print("[transform] DuckDB no disponible en este intérprete; usando motor pandas (fallback).", flush=True)
    try:
        met = _leer(con, str(raw / "meteorologia" / f"fecha={fecha}" / "*.parquet"), "meteorologia")
        aire = _leer(con, str(raw / "calidad_aire" / f"fecha={fecha}" / "*.parquet"), "calidad_aire")
        hidro = _leer(con, str(raw / "hidrologia" / f"fecha={fecha}" / "*.parquet"), "hidrologia")
    finally:
        if con is not None:
            con.close()

    salidas: dict = {}
    con2 = duckdb.connect() if _HAY_DUCKDB else None
    try:
        limpios: dict[str, pd.DataFrame] = {}
        for nombre, df in (("meteorologia", met), ("calidad_aire", aire), ("hidrologia", hidro)):
            if df is None or df.empty:
                print(f"[transform] {nombre}: vacío, se omite curated.", flush=True)
                continue
            # Validación con pandas (válida con y sin DuckDB; evita UPDATE sobre vista).
            limpio = df.copy()
            for col, (lo, hi) in RANGOS.items():
                if col in limpio.columns:
                    mask = limpio[col].notna() & ((limpio[col] < lo) | (limpio[col] > hi))
                    n = int(mask.sum())
                    if n:
                        print(f"[transform] {nombre}.{col}: {n} fuera de rango [{lo},{hi}] -> NULL", flush=True)
                        limpio.loc[mask, col] = None
            limpios[nombre] = limpio
            dest = lake / "curated" / nombre / f"fecha={fecha}"
            dest.mkdir(parents=True, exist_ok=True)
            limpio.to_parquet(dest / f"{nombre}.parquet", index=False)
            salidas[nombre] = str(dest)
            print(f"[transform] curated {nombre}: {len(limpio)} filas -> {dest}", flush=True)

        if not limpios:
            print("[transform] sin datos para oro.", flush=True)
            return salidas

        # --- Oro: outer join por punto_id con pandas (robusto, idempotente) ---
        base_cols = ["punto_id", "ciudad", "pais", "iso3", "region", "lat", "lon", "fecha"]
        oro: pd.DataFrame | None = None
        for nombre in ("meteorologia", "calidad_aire", "hidrologia"):
            df = limpios.get(nombre)
            if df is None:
                continue
            oro = df if oro is None else oro.merge(df, on="punto_id", how="outer", suffixes=("", f"_{nombre}"))
            # coalescer columnas base duplicadas con sufijo
            for c in base_cols[1:]:
                dup = f"{c}_{nombre}"
                if dup in oro.columns:
                    oro[c] = oro[c].combine_first(oro[dup])
                    oro = oro.drop(columns=[dup])
        assert oro is not None
        # fecha puede venir duplicada como fecha_meteorologia etc.; normalizar
        if "fecha" not in oro.columns:
            for alt in ("fecha_meteorologia", "fecha_calidad_aire", "fecha_hidrologia"):
                if alt in oro.columns:
                    oro["fecha"] = oro[alt]
                    break
        oro["fecha"] = oro["fecha"].fillna(fecha)
        # Contrato estable: fecha siempre string YYYY-MM-DD (evita timestamp vs partition).
        oro["fecha"] = pd.to_datetime(oro["fecha"]).dt.strftime("%Y-%m-%d")
        oro["categoria_pm25_aqi"] = oro["pm25_media"].apply(_categoria_pm25) if "pm25_media" in oro.columns else None

        d1 = lake / "serving" / "indicador_diario" / f"fecha={fecha}"
        d1.mkdir(parents=True, exist_ok=True)
        oro.to_parquet(d1 / "indicador_diario.parquet", index=False)
        salidas["indicador_diario"] = str(d1)
        print(f"[transform] oro indicador_diario: {len(oro)} filas -> {d1}", flush=True)

        agg_map = {"punto_id": ("n_puntos", "count")}
        if "temp_media_c" in oro.columns:
            agg_map["temp_media_c"] = ("temp_media_pais", "mean")
        if "precipitacion_mm" in oro.columns:
            agg_map["precipitacion_mm"] = ("precip_total_pais", "sum")
        if "pm25_media" in oro.columns:
            agg_map["pm25_media"] = ("pm25_media_pais", "mean")
        if "us_aqi_max" in oro.columns:
            agg_map["us_aqi_max"] = ("aqi_max_pais", "max")
        if "caudal_m3s" in oro.columns:
            agg_map["caudal_m3s"] = ("caudal_medio_pais", "mean")
        g = oro.groupby(["fecha", "iso3", "pais", "region"], as_index=False).agg(
            **{v[0]: (k, v[1]) for k, v in agg_map.items()}
        )
        d2 = lake / "serving" / "indicador_pais" / f"fecha={fecha}"
        d2.mkdir(parents=True, exist_ok=True)
        g.to_parquet(d2 / "indicador_pais.parquet", index=False)
        salidas["indicador_pais"] = str(d2)
        print(f"[transform] oro indicador_pais: {len(g)} filas -> {d2}", flush=True)
    finally:
        if con2 is not None:
            con2.close()

    for k, d in salidas.items():
        try:
            n = pq.read_table(d).num_rows
            print(f"[transform] verifica {k}: {n} filas", flush=True)
        except Exception:  # noqa: BLE001
            pass
    return salidas


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", required=True)
    ap.add_argument("--lake", default="lake")
    args = ap.parse_args(argv)
    transformar(args.fecha, args.lake)


if __name__ == "__main__":
    sys.exit(main())
