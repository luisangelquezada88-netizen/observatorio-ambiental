# Plan — Plataforma de Datos Ambientales y Biofísicos End-to-End

> Proyecto personal de ingeniería de datos: ingesta, orquestación, transformación y visualización de datos ambientales 100% abiertos, con despliegue rápido de un MVP y escalado progresivo.

---

## 1. Visión

Construir una plataforma de datos que integre **cinco pilares ambientales** con datos abiertos globales, orquestados con **Apache Airflow**, servidos en **PostGIS** y publicados como dashboard estático gratuito en **GitHub Pages** — sin costo alguno, con ruta de escalado clara hasta Spark/Sedona y Oracle Cloud si el volumen lo exige.

**Pilares:** calidad del aire · fuentes hídricas · meteorología/clima · deforestación · emisiones CO₂.

---

## 2. Decisiones tomadas (cerradas)

| Decisión | Elección | Justificación |
|---|---|---|
| Alcance geográfico | **Global con foco LatAm** | Las 5 fuentes ya son globales; el dashboard abre en LatAm con filtros para ver el mundo |
| Orquestador | **Apache Airflow** (batch, local desde el día 1) | Todas las fuentes son batch (diarias/anuales); Kafka queda fuera del MVP |
| Base de datos | **PostGIS desde el MVP** | Arquitectura completa desde el inicio; PGAdmin como cliente |
| Dashboard | **Quarto + Plotly/Folium** → HTML estático | GitHub Pages nunca duerme, cero costo, sin cold starts |
| Idioma | **Español** | Dashboard y documentación |
| Almacenamiento | **Parquet particionado** (lake local MinIO-compatible, rutas S3) | Portátil a R2/Oracle sin reescribir código |
| Despliegue MVP | **GitHub Pages + GitHub Actions (cron)** | Gratuito, automático, siempre en línea |
| Procesamiento | **DuckDB** (+ extensión spatial) | Suficiente hasta ~50 GB/query; Spark/Sedona solo si se necesita |

---

## 3. Fuentes de datos (MVP)

| Pilar | Fuente | API/Endpoint | Cadencia | Key |
|---|---|---|---|---|
| Calidad del aire | Open-Meteo Air Quality | PM2.5, PM10, O3, NO2 (CAMS/Copernicus) | Diaria | No |
| Hidrología | Open-Meteo River Discharge | Caudal diario (GloFAS) | Diaria | No |
| Meteorología | Open-Meteo Forecast + Histórico | Temp, precipitación, viento (ERA5) | Diaria | No |
| Deforestación | Global Forest Watch API | Tree cover loss anual por país/región | Mensual/anual | Registro gratuito (posible) |
| CO₂ | Our World in Data | CSV directo (GitHub raw) | Mensual | No |

**Nota Open-Meteo:** soporta múltiples coordenadas por request (listas separadas por comas) → ~150 puntos de monitoreo en **1-3 llamadas**, muy por debajo del límite gratuito de 10k calls/día.

**Distribución de puntos:** ~150 ubicaciones curadas (60% ciudades LatAm, 40% resto del mundo) definidas en un archivo de configuración versionado.

---

## 4. Arquitectura v0.1

```
                        LOCAL (docker-compose)                    CLOUD (GitHub)
┌──────────────────────────────────────────────────┐    ┌─────────────────────────────┐
│  Airflow (localhost:8080)                        │    │  GitHub Actions (cron)      │
│   ├─ DAG diario: Open-Meteo ×3                   │    │   ├─ python src/… (mismo    │
│   ├─ DAG mensual: GFW + OWID                     │    │   │  código que Airflow)   │
│   └─ DAG dashboard: render Quarto                │    │   └─ quarto render → Pages  │
│         │                                        │    │         │
│         ▼                                         │    └─────────────────────────────┘
│  LAKE (vol. montado, rutas S3-compatibles)       │              │
│   ├─ raw/  parquet por fecha (bronce)             │    ┌─────────────────────────────┐
│   ├─ curated/ parquet limpio (plata)             │    │  GitHub Pages (público)     │
│   └─ serving/ indicadores (oro)                   │    │  Dashboard Quarto estático │
│         │                                        │    │  5 páginas + mapa Folium    │
│         ▼                                         │    └─────────────────────────────┘
│  DuckDB: validación + agregaciones               │
│         │                                        │
│         ▼                                         │
│  PostGIS (servicio del compose, PGAdmin)         │
│   ├─ puntos de monitoreo (geometría)             │
│   └─ tablas de indicadores diarios/anuales       │
└──────────────────────────────────────────────────┘
```

**Principio "modo dual":** los scripts de `src/` no dependen del orquestador. Airflow los envuelve localmente (desarrollo y futura VM Oracle); GitHub Actions los invoca directamente en la nube para el despliegue diario. Un solo código, dos ejecutores.

---

## 5. Estructura del repo

```
plataforma-ambiental/
├── AGENTS.md                      # Convenciones para el loop agéntico
├── README.md                      # Setup, arquitectura, capturas
├── docker-compose.yml             # Airflow + PostGIS + MinIO + PGAdmin
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       └── pipeline.yml           # Cron diario: ingesta → transform → dashboard → Pages
├── Makefile                       # make up / make verify / make dashboard
├── dags/
│   ├── dag_ingesta_diaria.py      # 3 fuentes Open-Meteo
│   ├── dag_ingesta_mensual.py     # GFW + OWID
│   └── dag_dashboard.py           # Render Quarto
├── src/
│   ├── __init__.py
│   ├── config/
│   │   └── puntos_monitoreo.py    # ~150 ubicaciones (LatAm-foco)
│   ├── extract/
│   │   ├── openmeteo_calidad_aire.py
│   │   ├── openmeteo_hidrologia.py
│   │   ├── openmeteo_meteorologia.py
│   │   ├── gfw_deforestacion.py
│   │   └── owid_co2.py
│   ├── transform/
│   │   └── indicadores.py         # SQL DuckDB: bronce → plata → oro
│   └── load/
│       └── postgis.py             # Carga a PostGIS (geoalchemy2/psycopg)
├── sql/
│   ├── 01_schema_postgis.sql      # Extensiones, tablas, índices GiST
│   └── 02_validaciones.sql
├── dashboard/
│   ├── _quarto.yml                 # Sitio multi-página
│   ├── index.qmd                   # Resumen LatAm
│   ├── calidad_aire.qmd
│   ├── hidrologia.qmd
│   ├── meteorologia.qmd
│   ├── deforestacion.qmd
│   ├── emisiones.qmd
│   └── styles.css
├── tests/
│   └── test_pipeline.py           # Smoke: 1 día end-to-end
└── docs/
    ├── arquitectura.md
    └── decisiones.md              # Registro de decisiones (ADR ligero)
```

---

## 6. Etapas, hitos y tareas

### Etapa 0 — Fundaciones (½ día)

**Objetivo:** repo levantado, loop agéntico configurado.

- [ ] Crear repo GitHub (público) + clonar
- [ ] `docker-compose.yml`: Airflow (LocalExecutor) + PostGIS + MinIO + PGAdmin
- [ ] `AGENTS.md` (convenciones, criterios de aceptación, comando `make verify`)
- [ ] `Makefile` + `.env.example` + estructura de carpetas vacía
- [ ] Esqueleto de `puntos_monitoreo.py` con 10 ciudades de prueba

> **✅ Hito H0:** `docker compose up` levanta los 4 servicios en verde; Airflow UI accesible; `make verify` corre (aunque falle: es el esqueleto del loop).

### Etapa 1 — MVP desplegado rápido (3–5 días, o 2 sesiones sentadas)

**Objetivo:** pipeline diario end-to-end + dashboard público.

**1a. Ingesta Open-Meteo (día 1)**
- [ ] 3 extractores (calidad del aire, hidrología, meteorología) → `raw/` parquet particionado por fecha
- [ ] DAG diario con reintentos y idempotencia (misma fecha → sobrescribe, no duplica)
- [ ] Ampliar `puntos_monitoreo.py` a ~150 ubicaciones

> **✅ Hito H1:** DAG diario en verde en Airflow UI; parquet legible con DuckDB CLI.

**1b. Transformación y PostGIS (día 2)**
- [ ] `01_schema_postgis.sql`: tablas + geometría + índices GiST
- [ ] `transform/indicadores.py`: validación (nulos, rangos, unidades), agregados diarios/país
- [ ] `load/postgis.py`: carga idempotente (DELETE+INSERT por fecha o UPSERT)

> **✅ Hito H2:** `psql` devuelve indicadores del día por ciudad/país; geometrías visibles en PGAdmin.

**1c. Fuentes mensuales (día 3)**
- [ ] `gfw_deforestacion.py` (tree cover loss anual, países LatAm + top global)
- [ ] `owid_co2.py` (CSV → curated)
- [ ] DAG mensual

> **✅ Hito H3:** 5 pilares presentes en PostGIS.

**1d. Dashboard + despliegue (días 4–5)**
- [ ] Sitio Quarto: 5 páginas + índice, mapa Folium, gráficas Plotly
- [ ] `pipeline.yml`: Actions cron diario (ingesta → transform → render → Pages)
- [ ] README con capturas y arquitectura

> **✅ Hito H4 — MVP COMPLETO:** URL pública en GitHub Pages con datos de ayer, actualizándose sola cada día.

### Etapa 2 — Consolidación (v0.2, 1–2 semanas)

- [ ] Backfill histórico (ERA5 80 años en clima; GFW 2001–hoy)
- [ ] Migrar lake a rutas S3 reales (MinIO → R2 / Oracle Object Storage)
- [ ] Alertas básicas (umbral PM2.5 OMS, caudales extremos)
- [ ] Tests más serios (calidad de datos con dbt-style checks o Great Expectations)
- [ ] Fuentes adicionales: OpenAQ v3, estaciones oficiales LatAm (IDEAM, SINCA)
- [ ] CI: lint + tests en cada push

### Etapa 3 — Satélite y VM (v0.3)

- [ ] STAC + pystac-client: Sentinel-2, WorldCover
- [ ] MapBiomas (LatAm, cobertura del suelo)
- [ ] Desplegar el stack completo en **Oracle Cloud Always Free** (misma docker-compose, + Caddy HTTPS)
- [ ] Dominio propio

### Etapa 4 — Escala (v0.4+, condicional)

- [ ] **Spark + Sedona** solo si: joins espaciales masivos o raster continental (regla: cuando DuckDB se arrodille)
- [ ] **Kafka** solo si: sensores en tiempo real o alertas < 1 min
- [ ] Cualquiera de los dos se integra al lake existente **sin reescribir** lo anterior

---

## 7. Cronograma resumido

| Etapa | Duración estimada | Entregable visible |
|---|---|---|
| 0 — Fundaciones | ½ día | Compose en verde |
| 1 — MVP | 3–5 días | **Dashboard público actualizándose solo** |
| 2 — Consolidación | 1–2 semanas | Historia + alertas + calidad |
| 3 — Satélite/VM | 2–3 semanas | Imágenes satelitales + dominio propio |
| 4 — Escala | Bajo demanda | Spark/Kafka si el volumen lo exige |

---

## 8. Riesgos y mitigaciones

| Riesgo | Prob. | Mitigación |
|---|---|---|
| GFW API exige registro/token | Media | Fallback: OWID forest-change CSV, o diferir deforestación a v0.2 sin bloquear el MVP |
| Límites de rate Open-Meteo | Baja | Multicoordenada por request; cache local; backoff exponencial |
| Folium HTML pesado (> 1 MB) | Media | Simplificar geometrías (tolerancia), tile layers externos, muestrear puntos |
| Limpieza de datos sorpresiva (unidades, nulos) | Alta | Validaciones en transform desde H2; documentar cada anomalía en `docs/decisiones.md` |
| Pages límite 1 GB / ancho de banda | Baja | Solo HTML+JS estático; datos viven en parquet, no en el sitio |
| Sobre-ingeniería temprana | Alta | Regla: **nada de Etapa 2+ se toca antes del Hito H4** |

---

## 9. Reglas del proyecto

1. **H4 antes que todo lo demás.** El MVP desplegado vale más que cualquier mejora no desplegada.
2. **Modo dual:** cada script corre igual desde Airflow y desde Actions, sin if/else de orquestador.
3. **Idempotencia siempre:** re-ejecutar cualquier DAG un día dado produce el mismo resultado.
4. **El lake es la fuente de verdad;** PostGIS es solo serving. Todo se puede reconstruir desde `raw/`.
5. **Ningún secreto en el repo** (`.env` gitignored; en Pages/Actions solo APIs sin key o secrets de GitHub).
6. **Todo dato dudoso se documenta** en `docs/decisiones.md`, no se resuelve silenciosamente en código.

---

*Próximo paso concreto: Etapa 0 — crear el repo y levantar el `docker-compose.yml`.*
