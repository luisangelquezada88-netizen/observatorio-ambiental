"""Smoke de los chunks Python de dashboard/*.qmd sin Quarto (dev-only).
Extrae bloques ```{python}, los ejecuta con shims (display/show noop) y falla
si hay NameError, columnas inexistentes o datos rotos. No renderiza HTML.
Uso: python scripts/smoke_qmd.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT / "dashboard")
sys.path.insert(0, str(ROOT))
try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows: subíndices (O₃) en consola.
except Exception:  # noqa: BLE001
    pass

SHIM = (
    "def display(*a, **k):\n    return None\n"
    "import plotly.graph_objects as _go\n"
    "_go.Figure.show = lambda *a, **k: None\n"
)

BLOQUE = re.compile(r"```\{python[^}]*\}\n(.*?)```", re.DOTALL)


def main() -> int:
    fallos = 0
    for qmd in sorted(Path(".").glob("*.qmd")):
        bloques = BLOQUE.findall(qmd.read_text(encoding="utf-8"))
        if not bloques:
            print(f"[smoke] {qmd.name}: sin bloques python")
            continue
        codigo = SHIM + "\n".join(bloques)
        try:
            compile(codigo, qmd.name, "exec")
            exec(compile(codigo, qmd.name, "exec"), {"__name__": "__smoke__"})
            print(f"[smoke] {qmd.name}: OK ({len(bloques)} bloques)")
        except Exception as e:  # noqa: BLE001
            fallos += 1
            print(f"[smoke] {qmd.name}: FAIL {type(e).__name__}: {e}")
    print("[smoke] TODO OK" if not fallos else f"[smoke] {fallos} FALLOS")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
