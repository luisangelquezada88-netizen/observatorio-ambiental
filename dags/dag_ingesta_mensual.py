"""DAG mensual: GFW deforestación + OWID CO2 (año previo)."""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

ARGS = {"owner": "ambiental", "retries": 2, "retry_delay": timedelta(minutes=10)}

with DAG(
    dag_id="ingesta_mensual",
    start_date=datetime(2025, 1, 1),
    schedule="@monthly",
    catchup=False,
    default_args=ARGS,
    tags=["mvp", "gfw", "owid"],
) as dag:
    gfw = BashOperator(
        task_id="extract_gfw",
        bash_command="python -m src.extract.gfw_deforestacion --year {{ macros.ds_format(ds, '%Y-%m-%d', '%Y') | int - 1 }}",
    )
    co2 = BashOperator(
        task_id="extract_co2",
        bash_command="python -m src.extract.owid_co2 --year {{ macros.ds_format(ds, '%Y-%m-%d', '%Y') | int - 1 }}",
    )
    gfw >> co2
