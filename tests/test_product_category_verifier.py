"""Regression checks for backend-specific product-category build scope."""

import runpy
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

TASK = Path(__file__).resolve().parents[1] / "tasks" / "dbt-product-category-analytics"
TASK_RUN = (
    "dbt run --select stg_order_lines stg_products stg_categories "
    "stg_orders int_product_sales fct_category_performance"
)


@pytest.fixture
def pipeline():
    with patch("os.path.exists", return_value=False):
        module = runpy.run_path(str(TASK / "tests" / "test_outputs.py"))
    return module["run_dbt_pipeline"]


@pytest.mark.parametrize("backend", ["snowflake", "SNOWFLAKE"])
def test_snowflake_ignores_unrelated_model_failures(pipeline, monkeypatch, backend):
    monkeypatch.setenv("DB_TYPE", backend)
    commands = []

    def run_command(command):
        commands.append(command)
        return subprocess.CompletedProcess(
            command, 1 if command == "dbt run" else 0, stderr="unrelated model failed"
        )

    monkeypatch.setitem(pipeline.__globals__, "run_cmd", run_command)
    pipeline()
    assert commands == ["dbt deps", TASK_RUN]


@pytest.mark.parametrize("backend", [None, "duckdb"])
def test_duckdb_retains_existing_project_build(pipeline, monkeypatch, backend):
    if backend is None:
        monkeypatch.delenv("DB_TYPE", raising=False)
    else:
        monkeypatch.setenv("DB_TYPE", backend)
    commands = []

    def run_command(command):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stderr="")

    monkeypatch.setitem(pipeline.__globals__, "run_cmd", run_command)
    pipeline()
    assert commands == ["dbt deps", "dbt run"]


def test_snowflake_still_rejects_task_model_failure(pipeline, monkeypatch):
    monkeypatch.setenv("DB_TYPE", "snowflake")

    def run_command(command):
        return subprocess.CompletedProcess(
            command, 0 if command == "dbt deps" else 1, stderr="task model failed"
        )

    monkeypatch.setitem(pipeline.__globals__, "run_cmd", run_command)
    with pytest.raises(AssertionError, match="task model failed"):
        pipeline()
