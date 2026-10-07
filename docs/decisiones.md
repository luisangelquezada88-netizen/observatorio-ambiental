# Registro de decisiones (ADR ligero).
# Toda anomalía de datos va aquí, no silenciosa en código.

## D-01 — Unidades y rangos Open-Meteo (2026-10-07)
- Temperatura °C, precipitación mm, viento km/h (forecast daily ya convierte desde m/s).
- PM µg/m³, O₃ µg/m³, CO mg/m³→ el transform solo valida PM10/PM2.5/O₃/NO₂; CO se conserva crudo.
- Rangos de validación en `src/transform/indicadores.py::RANGOS`. Fuera de rango → NULL + log.

## D-02 — GloFAS malla gruesa (2026-10-07)
- `river_discharge` es caudal de celda ~10 km, no estación hidrométrica.
- En ciudades no-cuenca el valor es orientativo; el flag `es_cuenca` distingue puntos de río.
- Decisión: no filtrar ciudades; el dashboard advierte y el oro conserva todo.

## D-03 — GFW exige API key (2026-10-07)
- Data API GFW requiere `GFW_API_KEY` (registro gratuito).
- Sin key: `gfw_deforestacion.py` escribe partición canónica vacía para no bloquear H4.
- Fallback v0.2: OWID `forest-area` / Hansen. Dashboard muestra marcador hasta activar.

## D-04 — OWID CO₂ anual con retraso (2026-10-07)
- OWID publica con ~1 año de retraso; el DAG mensual pide `año previo`.
- Columnas canónicas: `co2` (Mt), `co2_per_capita` (t), `coal/oil/gas/cement_co2`.

## D-05 — PostGIS puerto 5433 en local (2026-10-07)
- Host usa 5432 interno, pero se publica en 5433 para no chocar con Postgres local.
- En compose: `POSTGIS_HOST=postgis`; en local/CI: `POSTGIS_HOST=localhost POSTGIS_PORT=5433`.

## D-06 — DuckDB opcional en Windows dev (2026-10-07)
- Python 3.14 Microsoft Store bloquea la DLL `_duckdb` (App Control) de forma intermitente.
- Decisión: `src/transform/indicadores.py` usa DuckDB si importa, si no fallback pandas
  con la misma semántica (rangos → NULL, mismos parquet). En Airflow (Linux) y Actions
  (ubuntu) DuckDB sí está activo; el contrato de datos no cambia.

## D-07 — MinIO opcional en compose + Airflow SequentialExecutor (2026-10-07)
- `minio/minio` desapareció de Docker Hub y `quay.io/minio/minio` exige auth (401).
  MinIO queda en perfil `minio` (`docker compose --profile minio up`); el lake local
  ya usa rutas S3-compatibles, así que no bloquea H0-H2.
- Airflow: `sqlalchemy>=2.0` en `_PIP_ADDITIONAL_REQUIREMENTS` rompía el arranque
  (Airflow 2.10 exige SQLAlchemy 1.4) → se quitó sqlalchemy/geoalchemy2 del contenedor
  (el load usa psycopg directo). Además `LocalExecutor+SQLite` está prohibido →
  `SequentialExecutor`, suficiente para DAGs secuenciales del MVP.

## D-08 — Flood API solo `river_discharge` + contrato `fecha` string (2026-10-07)
- La Flood API devuelve 400 con `river_discharge_{mean,median,max,min}` o con
  `forecast_days/past_days` combinados con `start/end_date`. Solo vale
  `daily=river_discharge` + rango de fechas; las columnas medio/max/min se
  rellenan con el mismo valor (un dato/dia) y `CHUNK` baja a 25.
- `fecha` en oro siempre string `YYYY-MM-DD` (`dt.strftime` en transform) y el
  load lee archivo concreto (no directorio Hive) para evitar el choque
  `timestamp vs string` de la columna de particion.

## D-09 — 429 en CI por IP compartida de GitHub (2026-10-07)
- Los runners de Actions comparten IPs de salida: Open-Meteo responde 429
  aunque estemos bajo 10k calls/dia. En local no ocurre.
- Mitigacion en `src/extract/_http.py`: respeta `Retry-After`, 6 intentos con
  backoff 5s->180s + jitter. Bloques de 20 puntos + pausa de 3s entre bloques.

## D-10 — Dashboard v2: híbrido tablero + pilares (2026-10-07)
- Se eliminan las páginas vacías (deforestación, CO₂) del render; git las conserva.
- Estructura: Tablero cruzado (KPIs + visor multicapa + scatter cruzados) y páginas
  temáticas (Aire/Clima/Agua) con visor propio. Híbrido > todo-junto (unidades
  incompatibles) y > solo-separado (sin análisis cruzado).
- Tiles: OSM + Esri (calles/satélite); CartoDB exige API key y queda vetado.
- KPIs como HTML precalculado (cero JS, apto para sitio estático).

## D-11 — Las "categorías OMS" eran breakpoints EPA (2026-10-07)
- Los cortes ≤12/35.4/55.4/150.4/250.4 son del AQI estadounidense, no de la OMS
  (la OMS 2021 solo da guía 24h ≤ 15 + objetivos 25/37.5/50/75).
- Corrección: columna `categoria_pm25_oms` → `categoria_pm25_aqi`
  (migración `sql/03_aqi_rename.sql`), etiquetas "AQI (EE. UU.)" y línea verde
  OMS-15 en gráficos. Detectado en revisión pre-fase-2.

## D-12 — Historial versionado para el slider temporal (2026-10-07)
- El runner de Actions es efímero: sin persistencia no hay serie temporal.
  El workflow commitea `lake/serving` al repo en cada run (~30 KB/día).
- `lake/serving/**/*.parquet` sale de `.gitignore` (negación); raw/curated
  siguen ignorados. No hay loop infinito: `lake/**` no está en el trigger.
- Semilla inicial: backfill manual de 4 días; desde ahí el cron acumula solo.
