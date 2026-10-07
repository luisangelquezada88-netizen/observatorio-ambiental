"""DAG diario: 3 fuentes Open-Meteo → transform → PostGIS.
Solo envuelve src/ (sin lógica de negocio). Idempotente por {{ ds }}.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

ARGS = {"owner": "ambiental", "retries": 3, "retry_delay": timedelta(minutes=5)}

with DAG(
    dag_id="ingesta_diaria",
    start_date=datetime(2025, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args=ARGS,
    tags=["mvp", "open-meteo"],
    doc_md="Ingesta diaria Open-Meteo x3 + transform + PostGIS. Idempotente por ds.",
) as dag:
    meteo = BashOperator(
        task_id="extract_meteorologia",
        bash_command="python -m src.extract.openmeteo_meteorologia --fecha {{ ds }}",
    )
    aire = BashOperator(
        task_id="extract_calidad_aire",
        bash_command="python -m src.extract.openmeteo_calidad_aire --fecha {{ ds }}",
    )
    hidro = BashOperator(
        task_id="extract_hidrologia",
        bash_command="python -m src.extract.openmeteo_hidrologia --fecha {{ ds }}",
    )
    transform = BashOperator(
        task_id="transform_indicadores",
        bash_command="python -m src.transform.indicadores --fecha {{ ds }}",
    )
    load = BashOperator(
        task_id="load_postgis",
        bash_command="python -m src.load.postgis --fecha {{ ds }}",
    )
    superficie = BashOperator(
        task_id="superficie_idw",
        bash_command="python -m src.transform.superficie_idw --fecha {{ ds }}",
    )

    [meteo, aire, hidro] >> transform >> [load, superficie]
