-- 01_schema_postgis.sql — Esquema serving (re-ejecutable: IF NOT EXISTS).
-- PostGIS desde el MVP (plan §2). El lake es la fuente de verdad; estas tablas
-- se reconstruyen con DELETE+INSERT por fecha desde lake/serving.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS puntos_monitoreo (
  punto_id TEXT PRIMARY KEY,
  ciudad   TEXT NOT NULL,
  pais     TEXT NOT NULL,
  iso3     CHAR(3) NOT NULL,
  region   TEXT NOT NULL CHECK (region IN ('LatAm','Mundo')),
  tipo     TEXT NOT NULL DEFAULT 'ciudad' CHECK (tipo IN ('ciudad','cuenca')),
  geom     geometry(Point, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_puntos_geom ON puntos_monitoreo USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_puntos_region ON puntos_monitoreo (region);

CREATE TABLE IF NOT EXISTS indicador_diario (
  punto_id TEXT NOT NULL REFERENCES puntos_monitoreo(punto_id),
  fecha DATE NOT NULL,
  temp_max_c DOUBLE PRECISION,
  temp_min_c DOUBLE PRECISION,
  temp_media_c DOUBLE PRECISION,
  precipitacion_mm DOUBLE PRECISION,
  viento_max_kmh DOUBLE PRECISION,
  pm25_media DOUBLE PRECISION,
  pm25_max DOUBLE PRECISION,
  pm10_media DOUBLE PRECISION,
  o3_media DOUBLE PRECISION,
  no2_media DOUBLE PRECISION,
  us_aqi_media DOUBLE PRECISION,
  us_aqi_max DOUBLE PRECISION,
  categoria_pm25_oms TEXT,
  caudal_m3s DOUBLE PRECISION,
  caudal_medio_m3s DOUBLE PRECISION,
  caudal_max_m3s DOUBLE PRECISION,
  PRIMARY KEY (punto_id, fecha)
);
CREATE INDEX IF NOT EXISTS idx_diario_fecha ON indicador_diario (fecha);
CREATE INDEX IF NOT EXISTS idx_diario_iso ON indicador_diario (punto_id);

CREATE TABLE IF NOT EXISTS indicador_pais (
  fecha DATE NOT NULL,
  iso3 CHAR(3) NOT NULL,
  pais TEXT NOT NULL,
  region TEXT NOT NULL,
  n_puntos INTEGER NOT NULL,
  temp_media_pais DOUBLE PRECISION,
  precip_total_pais DOUBLE PRECISION,
  pm25_media_pais DOUBLE PRECISION,
  aqi_max_pais DOUBLE PRECISION,
  caudal_medio_pais DOUBLE PRECISION,
  PRIMARY KEY (fecha, iso3)
);
CREATE INDEX IF NOT EXISTS idx_pais_fecha ON indicador_pais (fecha);

CREATE TABLE IF NOT EXISTS co2_anual (
  iso3 CHAR(3) NOT NULL,
  anio INTEGER NOT NULL,
  pais TEXT,
  co2_mt DOUBLE PRECISION,
  co2_per_capita DOUBLE PRECISION,
  fuente TEXT DEFAULT 'OWID co2-data',
  PRIMARY KEY (iso3, anio)
);

CREATE TABLE IF NOT EXISTS deforestacion_anual (
  iso3 CHAR(3) NOT NULL,
  anio INTEGER NOT NULL,
  perdida_ha DOUBLE PRECISION,
  fuente TEXT DEFAULT 'GFW umd_tree_cover_loss',
  PRIMARY KEY (iso3, anio)
);
