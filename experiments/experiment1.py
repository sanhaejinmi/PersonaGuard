"""
실험 1 — 개인정보 숨은그림찾기 (§6).

Recall이 가장 중요하다 — 위험한 정보를 놓치면 그대로 밖으로 새어나갈 수 있기
때문이다 (§6 마지막 문단). 그래서 overall/타입별 지표와 별개로 위험도(risk)별
Recall을 항상 같이 계산한다.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from experiments.dataset import TestCase
from experiments.matching import PRF, match_entities

Detector = Callable[[str], list[dict]]


@dataclass
class Experiment1Result:
    detector_name: str
    overall: PRF
    by_type: dict[str, PRF]
    by_risk: dict[int, PRF]
    missed: list[dict] = field(default_factory=list)  # FN — 놓친 사례
    false_alarms: list[dict] = field(default_factory=list)  # FP — 잘못 찾은 사례

    def as_dict(self) -> dict:
        return {
            "detector_name": self.detector_name,
            "overall": self.overall.as_dict(),
            "by_type": {t: prf.as_dict() for t, prf in self.by_type.items()},
            "by_risk": {r: prf.as_dict() for r, prf in self.by_risk.items()},
            "missed": self.missed,
            "false_alarms": self.false_alarms,
        }


def run_experiment1(
    cases: list[TestCase],
    detectors: dict[str, Detector],
    iou_threshold: float = 0.5,
) -> dict[str, Experiment1Result]:
    results: dict[str, Experiment1Result] = {}

    for name, detector in detectors.items():
        type_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # tp, fp, fn
        risk_counts: dict[int, list[int]] = defaultdict(lambda: [0, 0, 0])
        missed: list[dict] = []
        false_alarms: list[dict] = []
        total_tp = total_fp = total_fn = 0

        for case in cases:
            gold = case.gold_entities
            pred = detector(case.v1_prompt)

            matches, unmatched_gold, unmatched_pred = match_entities(
                gold, pred, iou_threshold=iou_threshold
            )

            for gi, _pi, _iou in matches:
                g = gold[gi]
                type_counts[g.type][0] += 1
                risk_counts[g.risk][0] += 1
                total_tp += 1

            for gi in unmatched_gold:
                g = gold[gi]
                type_counts[g.type][2] += 1
                risk_counts[g.risk][2] += 1
                total_fn += 1
                missed.append(
                    {"case_id": case.id, "type": g.type, "text": g.text, "risk": g.risk}
                )

            for pi in unmatched_pred:
                p = pred[pi]
                type_counts[p["type"]][1] += 1
                # 예측이 잘못됐을 때 어느 위험도였는지는 정답 기준이 없으므로 risk별 집계에는 넣지 않는다.
                total_fp += 1
                false_alarms.append(
                    {"case_id": case.id, "type": p["type"], "value": p.get("value", "")}
                )

        results[name] = Experiment1Result(
            detector_name=name,
            overall=PRF(total_tp, total_fp, total_fn),
            by_type={t: PRF(*counts) for t, counts in type_counts.items()},
            by_risk={r: PRF(*counts) for r, counts in risk_counts.items()},
            missed=missed,
            false_alarms=false_alarms,
        )

    return results
