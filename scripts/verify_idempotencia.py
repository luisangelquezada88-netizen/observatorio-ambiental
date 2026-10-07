"""Verificación idempotencia: 2 corridas misma fecha → mismo nº filas.
Uso: python scripts/verify_idempotencia.py --fecha YYYY-MM-DD [--lake lake]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pyarrow.parquet as pq


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fecha", required=True)
    ap.add_argument("--lake", default="lake")
    args = ap.parse_args(argv)

    from src.transform.indicadores import transformar

    s1 = transformar(args.fecha, args.lake)
    n1 = {k: pq.read_table(v).num_rows for k, v in s1.items()}
    s2 = transformar(args.fecha, args.lake)
    n2 = {k: pq.read_table(v).num_rows for k, v in s2.items()}
    print(f"[verify] corrida1={n1}", flush=True)
    print(f"[verify] corrida2={n2}", flush=True)
    if n1 != n2:
        print("[verify] FAIL: idempotencia rota", flush=True)
        return 1
    print("[verify] OK: idempotente", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
