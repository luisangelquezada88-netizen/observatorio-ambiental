# Plataforma de Datos Ambientales y Biofísicos End-to-End

Ingesta · orquestación · transformación · PostGIS · dashboard estático.
5 pilares con datos 100% abiertos. Detalle del plan en [`plan.md`](plan.md).

## Inicio rápido (Etapa 0)

```bash
cp .env.example .env
docker compose up -d        # o: make up
docker compose ps           # 4 servicios en verde
```

| Servicio | URL | Credenciales dev |
|---|---|---|
| Airflow | http://localhost:8080 | admin / admin |
| PGAdmin | http://localhost:5050 | admin@local.dev / admin |
| PostGIS | localhost:5433 | ambiental / ambiental_dev |
| MinIO consola | http://localhost:9001 | minioadmin / minioadmin123 |

## Pipeline diario (modo dual)

```bash
# Local (misma CLI que Airflow y Actions):
python -m src.extract.openmeteo_meteorologia --fecha 2025-01-15
python -m src.extract.openmeteo_calidad_aire --fecha 2025-01-15
python -m src.extract.openmeteo_hidrologia --fecha 2025-01-15
python -m src.transform.indicadores --fecha 2025-01-15
python -m src.load.postgis --fecha 2025-01-15   # requiere compose en verde
pytest tests/ -q
```

Fuentes mensuales:

```bash
python -m src.extract.owid_co2 --year 2023
python -m src.extract.gfw_deforestacion --year 2023  # sin GFW_API_KEY: partición vacía (D-03)
```

Dashboard local (requiere [Quarto](https://quarto.org)):

```bash
quarto render dashboard --to html   # o: make dashboard
```

## Estructura

```
src/config/puntos_monitoreo.py  # ~150 puntos (60% LatAm)
src/extract/*  src/transform/indicadores.py  src/load/postgis.py
dags/  sql/  dashboard/*.qmd  tests/  docs/  lake/
```

## Reglas

Ver [`AGENTS.md`](AGENTS.md): modo dual, idempotencia, lake como fuente de verdad,
sin secretos, anomalías en `docs/decisiones.md`.
