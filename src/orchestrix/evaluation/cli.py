"""Evaluation CLI — point d'entrée pour `python -m orchestrix.evaluation.cli`.

Usage :
  python -m orchestrix.evaluation.cli run --benchmark data/benchmarks/safe_unsafe_v1.json
  python -m orchestrix.evaluation.cli compare --current ... --baseline ...
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import click

logger = logging.getLogger(__name__)


@click.group()
def cli() -> None:
    """ORCHESTRIX — Suite d'évaluation."""


@cli.command()
@click.option("--benchmark", required=True, type=click.Path(exists=True))
@click.option("--output", required=True, type=click.Path())
@click.option("--mode", default="dev", type=click.Choice(["dev", "ci", "full"]))
def run(benchmark: str, output: str, mode: str) -> None:
    """Lance la suite d'évaluation."""
    logger.info("Running evaluation: benchmark=%s mode=%s", benchmark, mode)
    # TODO: implémenter l'exécution réelle de la suite
    #   1. Charger le benchmark
    #   2. Pour chaque scénario : invoquer Scoping Agent + ActionGuard (mock)
    #   3. Collecter les métriques (RQ1-RQ4)
    #   4. Sauvegarder dans output (JSON)
    result = {
        "benchmark": benchmark,
        "mode": mode,
        "metrics": {},
        "note": "À implémenter — voir src/orchestrix/evaluation/cli.py",
    }
    Path(output).write_text(json.dumps(result, indent=2))
    click.echo(f"✓ Résultats écrits dans {output}")


@cli.command()
@click.option("--current", required=True, type=click.Path(exists=True))
@click.option("--baseline", required=True, type=click.Path(exists=True))
@click.option("--gate-config", required=True, type=click.Path(exists=True))
def compare(current: str, baseline: str, gate_config: str) -> None:
    """Compare un run au baseline et applique les gates."""
    logger.info("Comparing %s vs %s", current, baseline)
    # TODO: charger les deux JSON, lire les gates, décider PASS/FAIL
    raise NotImplementedError("compare : à implémenter (cf. .github/eval_gate.json)")


if __name__ == "__main__":
    cli()
