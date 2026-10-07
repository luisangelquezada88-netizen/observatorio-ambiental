"""DAG dashboard: render Quarto estático (lee lake/serving, nunca PostGIS)."""
from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="dashboard",
    start_date=datetime(2025, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args={"owner": "ambiental", "retries": 1},
    tags=["mvp", "quarto"],
) as dag:
    BashOperator(
        task_id="render_quarto",
        bash_command="quarto render dashboard --to html",
    )
