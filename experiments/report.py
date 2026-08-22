"""실험 1·2·3 결과를 CSV/JSON으로 정리하는 유틸리티."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from experiments.experiment1 import Experiment1Result
from experiments.experiment2 import Experiment2Summary


def experiment1_summary_table(results: dict[str, Experiment1Result]) -> list[dict]:
    return [
        {
            "detector": name,
            **res.overall.as_dict(),
        }
        for name, res in results.items()
    ]


def experiment1_by_type_table(results: dict[str, Experiment1Result]) -> list[dict]:
    rows = []
    for name, res in results.items():
        for entity_type, prf in res.by_type.items():
            rows.append({"detector": name, "type": entity_type, **prf.as_dict()})
    return rows


def experiment1_by_risk_table(results: dict[str, Experiment1Result]) -> list[dict]:
    rows = []
    for name, res in results.items():
        for risk, prf in sorted(res.by_risk.items()):
            rows.append({"detector": name, "risk": risk, **prf.as_dict()})
    return rows


def experiment2_summary_table(summaries: list[Experiment2Summary]) -> list[dict]:
    return [
        {
            "mode": s.mode,
            "n_cases": s.n_cases,
            "leakage_rate": round(s.leakage_rate, 4),
            "over_masking_rate": round(s.over_masking_rate, 4),
            "action_accuracy": round(s.action_accuracy, 4),
            "format_accuracy": round(s.format_accuracy, 4) if s.format_accuracy is not None else "",
            "consistency_violation_count": s.consistency_violation_count,
        }
        for s in summaries
    ]


def write_csv(rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(obj, path: str | Path) -> None:
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
