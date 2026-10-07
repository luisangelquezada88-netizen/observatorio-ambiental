"""HTTP resiliente para las APIs Open-Meteo (modo dual: sin estado, sin orquestador).

- Respeta 429 + cabecera `Retry-After` (los runners de GitHub comparten IP
  de salida y Open-Meteo los throttea aunque estemos bajo 10k calls/día).
- Backoff exponencial con jitter ante 5xx/timeouts.
- Todo a stdout con prefijo [http] para que quede en los logs de Actions.
"""
from __future__ import annotations

import random
import time

import requests

REINTENTOS = 6
BASE_SEG = 5
TOPE_SEG = 180


def _espera_429(resp: requests.Response, intento: int) -> float:
    try:
        ra = float(resp.headers.get("Retry-After", ""))
        if ra > 0:
            return min(ra + random.uniform(0, 3), TOPE_SEG)
    except (TypeError, ValueError):
        pass
    return min(BASE_SEG * (2 ** (intento - 1)) + random.uniform(0, 3), TOPE_SEG)


def get_json(url: str, params: dict, etiqueta: str, timeout: int = 90) -> list[dict] | dict:
    last_err: Exception | None = None
    for intento in range(1, REINTENTOS + 1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 429:
                espera = _espera_429(r, intento)
                print(f"[http:{etiqueta}] 429 (intento {intento}/{REINTENTOS}); espero {espera:.0f}s", flush=True)
                time.sleep(espera)
                continue
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            last_err = e
            espera = min(BASE_SEG * (2 ** (intento - 1)) + random.uniform(0, 3), TOPE_SEG)
            print(f"[http:{etiqueta}] HTTP {e} (intento {intento}/{REINTENTOS}); espero {espera:.0f}s", flush=True)
            time.sleep(espera)
        except Exception as e:  # noqa: BLE001 - timeouts, red, etc.
            last_err = e
            espera = min(BASE_SEG * (2 ** (intento - 1)) + random.uniform(0, 3), TOPE_SEG)
            print(f"[http:{etiqueta}] {type(e).__name__}: {e} (intento {intento}/{REINTENTOS}); espero {espera:.0f}s", flush=True)
            time.sleep(espera)
    raise RuntimeError(f"[http:{etiqueta}] API falló tras {REINTENTOS} intentos: {last_err}")
