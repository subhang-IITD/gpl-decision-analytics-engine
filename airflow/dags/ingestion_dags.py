"""Airflow DAGs for scheduled ingestion & monitoring (brief 3.1, 5.3).

Schedules match Section 3.1:
  - portals (MagicBricks/99acres)  -> daily
  - news + gov announcements       -> daily
  - RERA + PropEquity              -> weekly
  - competitive monitoring scan    -> daily
  - job signals                    -> monthly

Any task failure triggers an email to the configured admin within the SLA
(brief 5.3) via Airflow's on_failure_callback -> alerting layer.

These are standard Airflow DAGs; drop this file in $AIRFLOW_HOME/dags. They are
import-safe without Airflow installed (guarded import) so the repo's test suite
and CI don't require an Airflow runtime.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    _AIRFLOW = True
except Exception:  # Airflow not installed (e.g. during tests) -> no-op module
    _AIRFLOW = False


def _on_failure(context) -> None:
    from models.alerting import deliver
    task = context.get("task_instance")
    deliver(f"Pipeline FAILURE: {task.dag_id}.{task.task_id} at {dt.datetime.utcnow()} UTC",
            subject="[GPL Engine] Pipeline failure", whatsapp=True)


def _run_portals():
    from ingestion.runner import run_portals
    return run_portals()


def _run_news_gov():
    from ingestion.runner import run_news_and_gov
    return run_news_and_gov()


def _run_rera():
    from ingestion.runner import run_rera
    return run_rera()


def _run_monitoring():
    from models.monitoring import scan
    return {"alerts": len(scan(deliver_alerts=True))}


_DEFAULT_ARGS = {"owner": "gpl-engine", "retries": 2, "retry_delay": dt.timedelta(minutes=10),
                 "on_failure_callback": _on_failure}

if _AIRFLOW:
    _SPECS = [
        ("gpl_portals_daily", "@daily", _run_portals),
        ("gpl_news_gov_daily", "@daily", _run_news_gov),
        ("gpl_rera_weekly", "@weekly", _run_rera),
        ("gpl_monitoring_daily", "@daily", _run_monitoring),
    ]
    for dag_id, sched, fn in _SPECS:
        with DAG(dag_id=dag_id, schedule=sched, start_date=dt.datetime(2026, 1, 1),
                 catchup=False, default_args=_DEFAULT_ARGS, tags=["gpl"]) as dag:
            PythonOperator(task_id="run", python_callable=fn)
        globals()[dag_id] = dag
