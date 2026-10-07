# Arquitectura v0.1

Ver `plan.md §4`. Resumen operativo:

```
Open-Meteo x3 (diario) ─┐
GFW (anual, con key) ───┼─▶ lake/raw/fecha=.../*.parquet (bronce)
OWID CO₂ (anual) ───────┘
        │ DuckDB valida rangos (D-01) y agrega
        ▼
lake/curated/*/fecha=* (plata) ─▶ lake/serving/indicador_{diario,pais}/fecha=* (oro)
        │ DELETE+INSERT por fecha
        ▼
PostGIS (serving reconstruible) ◀── sql/01_schema_postgis.sql
        │ dashboard lee parquet, nunca PostGIS (Pages estático)
        ▼
Quarto → GitHub Pages (cron Actions diario)
```

## Modo dual

`src/` no sabe quién lo llama. Airflow (`dags/`) y GitHub Actions
(`.github/workflows/pipeline.yml`) invocan el mismo CLI:

```
python -m src.extract.openmeteo_meteorologia --fecha YYYY-MM-DD
python -m src.extract.openmeteo_calidad_aire --fecha YYYY-MM-DD
python -m src.extract.openmeteo_hidrologia --fecha YYYY-MM-DD
python -m src.transform.indicadores --fecha YYYY-MM-DD
python -m src.load.postgis --fecha YYYY-MM-DD   # solo local/compose
```

## Lake

Parquet particionado Hive: `lake/<capa>/<fuente>/fecha=YYYY-MM-DD/*.parquet`.
La fuente de verdad es `lake/raw`; todo se reconstruye desde ahí (regla 4).

## Escalado (Etapas 2-4)

- Rutas S3-compatibles → migrar `lake/` a MinIO→R2/Oracle sin reescribir.
- DuckDB hasta ~50 GB/query; Spark/Sedona solo si se arrodilla.
- Kafka solo si hay sensores <1 min. Nada de esto antes del Hito H4.
