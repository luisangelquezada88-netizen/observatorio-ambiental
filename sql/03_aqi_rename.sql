-- 03_aqi_rename.sql — Corrección D-11: la columna era EPA, no OMS.
-- Re-ejecutable; en instalaciones nuevas 01_schema ya crea categoria_pm25_aqi.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'indicador_diario' AND column_name = 'categoria_pm25_oms'
  ) THEN
    ALTER TABLE indicador_diario RENAME COLUMN categoria_pm25_oms TO categoria_pm25_aqi;
  END IF;
END
$$;
ALTER TABLE indicador_diario ADD COLUMN IF NOT EXISTS categoria_pm25_aqi TEXT;
