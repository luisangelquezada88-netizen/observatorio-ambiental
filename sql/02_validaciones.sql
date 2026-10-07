-- 02_validaciones.sql — Chequeos de calidad re-ejecutables (SELECT, no mutan).
-- Criterio: cero filas = datos sanos para la fecha de referencia.

-- 1. Coordenadas fuera del mundo válido
SELECT punto_id, ciudad FROM puntos_monitoreo
WHERE ST_X(geom) NOT BETWEEN -180 AND 180 OR ST_Y(geom) NOT BETWEEN -90 AND 90;

-- 2. Temperaturas físicamente imposibles (ver D-01 en docs/decisiones.md)
SELECT punto_id, fecha, temp_max_c, temp_min_c FROM indicador_diario
WHERE temp_max_c NOT BETWEEN -60 AND 55 OR temp_min_c NOT BETWEEN -60 AND 55;

-- 3. PM2.5 negativo o extremo (>1000 µg/m³ sugiere error de unidades)
SELECT punto_id, fecha, pm25_media FROM indicador_diario
WHERE pm25_media IS NOT NULL AND (pm25_media < 0 OR pm25_media > 1000);

-- 4. Caudales negativos o absurdos (>300 000 m³/s, Amazonas ~209 000)
SELECT punto_id, fecha, caudal_m3s FROM indicador_diario
WHERE caudal_m3s IS NOT NULL AND (caudal_m3s < 0 OR caudal_m3s > 300000);

-- 5. Puntos sin dato diario (cobertura de la última fecha cargada)
SELECT p.punto_id, p.ciudad FROM puntos_monitoreo p
LEFT JOIN indicador_diario d ON d.punto_id = p.punto_id AND d.fecha = (SELECT MAX(fecha) FROM indicador_diario)
WHERE d.punto_id IS NULL;

-- 6. Duplicados (debería dar 0 por PK; si da >0, falló la idempotencia)
SELECT punto_id, fecha, COUNT(*) FROM indicador_diario GROUP BY 1,2 HAVING COUNT(*) > 1;
SELECT fecha, iso3, COUNT(*) FROM indicador_pais GROUP BY 1,2 HAVING COUNT(*) > 1;

-- 7. Resumen diario por país (consulta de humo H2)
SELECT fecha, iso3, n_puntos, ROUND(temp_media_pais::numeric,1) AS t_media,
       ROUND(pm25_media_pais::numeric,1) AS pm25
FROM indicador_pais ORDER BY fecha DESC, iso3 LIMIT 50;
