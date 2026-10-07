"""Carga idempotente a PostGIS desde lake/serving (DELETE+INSERT por fecha).
CLI: python -m src.load.postgis --fecha YYYY-MM-DD [--lake lake]
Tablas: puntos_monitoreo, indicador_diario, indicador_pais (ver sql/01_schema_postgis.sql).
Si no hay PostGIS accesible, falla con mensaje claro (el dashboard no lo necesita).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd


def _conn():
    import psycopg

    return psycopg.connect(
        host=os.getenv("POSTGIS_HOST", "localhost"),
        port=int(os.getenv("POSTGIS_PORT", "5433")),
        dbname=os.getenv("POSTGIS_DB", "ambiental"),
        user=os.getenv("POSTGIS_USER", "ambiental"),
        password=os.getenv("POSTGIS_PASSWORD", "ambiental_dev"),
        connect_timeout=10,
    )


def _read(path: Path) -> pd.DataFrame | None:
    try:
        # Acepta archivo o directorio (no el glob Hive): evita que pyarrow
        # inyecte la columna de partición `fecha=...` y choque de tipos.
        fich = [path] if path.is_file() else sorted(path.glob("*.parquet"))
        if not fich:
            raise FileNotFoundError(path)
        df = pd.concat([pd.read_parquet(f) for f in fich], ignore_index=True)
        if "fecha" in df.columns:
            df["fecha"] = pd.to_datetime(df["fecha"]).dt.strftime("%Y-%m-%d")
        return df
    except Exception as e:  # noqa: BLE001
        print(f"[load] sin datos en {path}: {e}", flush=True)
        return None


def cargar(fecha: str, lake: str | Path = "lake") -> dict:
    from src.config.puntos_monitoreo import PUNTOS

    lake = Path(lake)
    diario = _read(lake / "serving" / "indicador_diario" / f"fecha={fecha}" / "indicador_diario.parquet")
    pais = _read(lake / "serving" / "indicador_pais" / f"fecha={fecha}" / "indicador_pais.parquet")
    resumen = {"fecha": fecha}
    try:
        conn = _conn()
    except Exception as e:  # noqa: BLE001
        print(f"[load] PostGIS no accesible: {e}", flush=True)
        print("[load] Sugerencia: make up  (o exporta POSTGIS_HOST=localhost POSTGIS_PORT=5433)", flush=True)
        raise SystemExit(2) from e

    with conn, conn.cursor() as cur:
        # 1) Upsert puntos de monitoreo (dimensión geográfica estable).
        cur.executemany(
            """
            INSERT INTO puntos_monitoreo (punto_id, ciudad, pais, iso3, region, tipo, geom)
            VALUES (%s,%s,%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326))
            ON CONFLICT (punto_id) DO UPDATE SET
              ciudad=EXCLUDED.ciudad, pais=EXCLUDED.pais, iso3=EXCLUDED.iso3,
              region=EXCLUDED.region, tipo=EXCLUDED.tipo, geom=EXCLUDED.geom
            """,
            [(p["id"], p["ciudad"], p["pais"], p["iso3"], p["region"], p["tipo"], p["lon"], p["lat"]) for p in PUNTOS],
        )
        resumen["puntos"] = len(PUNTOS)
        # 2) DELETE+INSERT diario (idempotencia).
        cur.execute("DELETE FROM indicador_diario WHERE fecha = %s", (fecha,))
        n_d = 0
        if diario is not None and not diario.empty:
            cols = ["punto_id", "fecha", "temp_max_c", "temp_min_c", "temp_media_c", "precipitacion_mm",
                    "viento_max_kmh", "pm25_media", "pm25_max", "pm10_media", "o3_media", "no2_media",
                    "us_aqi_media", "us_aqi_max", "categoria_pm25_aqi", "caudal_m3s", "caudal_medio_m3s", "caudal_max_m3s"]
            cols = [c for c in cols if c in diario.columns]
            cur.executemany(
                f"INSERT INTO indicador_diario ({','.join(cols)}) VALUES ({','.join(['%s'] * len(cols))})",
                [tuple(r.get(c) if not (isinstance(r.get(c), float) and pd.isna(r.get(c))) else None for c in cols)
                 for r in diario.to_dict("records")],
            )
            n_d = len(diario)
        resumen["diario"] = n_d
        # 3) DELETE+INSERT país.
        cur.execute("DELETE FROM indicador_pais WHERE fecha = %s", (fecha,))
        n_p = 0
        if pais is not None and not pais.empty:
            cols = ["fecha", "iso3", "pais", "region", "n_puntos", "temp_media_pais",
                    "precip_total_pais", "pm25_media_pais", "aqi_max_pais", "caudal_medio_pais"]
            cols = [c for c in cols if c in pais.columns]
            cur.executemany(
                f"INSERT INTO indicador_pais ({','.join(cols)}) VALUES ({','.join(['%s'] * len(cols))})",
                [tuple(r.get(c) if not (isinstance(r.get(c), float) and pd.isna(r.get(c))) else None for c in cols)
                 for r in pais.to_dict("records")],
            )
            n_p = len(pais)
        resumen["pais"] = n_p
    conn.close()
    print(f"[load] fecha={fecha} puntos={resumen['puntos']} diario={resumen['diario']} pais={resumen['pais']}", flush=True)
    return resumen


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", required=True)
    ap.add_argument("--lake", default="lake")
    args = ap.parse_args(argv)
    cargar(args.fecha, args.lake)


if __name__ == "__main__":
    sys.exit(main())
