#!/usr/bin/env python3
"""실험 2 실행기 — 2-A(오라클 span) / 2-B(전체 파이프라인)를 split별로 돌리고 결과를 저장한다.

실행 (레포 루트 = PersonaGuard-develop\\PersonaGuard-develop 에서):

    # 2-A : Ollama 필요 없음, 몇 초면 끝남
    python -m experiments.run_exp2 --mode 2a --splits dev val test challenge --out experiments\\out\\exp2a

    # 2-B : Ollama 켜져 있어야 함. test 750건은 오래 걸리므로 먼저 --limit 로 확인
    python -m experiments.run_exp2 --mode 2b --splits dev --limit 5 --out experiments\\out\\exp2b_smoke
    python -m experiments.run_exp2 --mode 2b --splits dev val --out experiments\\out\\exp2b

출력 (--out 폴더):
    summary.json          split별 지표
    summary.csv           같은 내용 표
    action_mismatch.csv   POLICY와 사람 라벨이 갈린 항목 (타입·gold action별 집계)
    per_case.jsonl        문항별 원자료 (누출/과다마스킹/일관성 위반 목록 포함)
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from experiments.dataset import load_dataset
from experiments.experiment2 import run_experiment2a, run_experiment2b
from experiments.masking_eval import GOLD_ACTION_TO_POLICY_ACTION
from app.actions.policy import POLICY

DATA = Path("experiments/data")


def action_mismatch(cases) -> Counter:
    """POLICY가 고르는 액션과 사람이 정한 정답 처리방법이 갈린 항목을 (타입, gold action)로 센다."""
    bad: Counter = Counter()
    for c in cases:
        for g in c.gold_entities:
            expected = GOLD_ACTION_TO_POLICY_ACTION[g.action]
            actual = "keep" if expected == "keep" else POLICY.get(g.type, "mask")
            if actual != expected:
                bad[(g.type, g.action, expected, actual)] += 1
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("2a", "2b"), required=True)
    ap.add_argument("--splits", nargs="+", default=["dev"])
    ap.add_argument("--limit", type=int, default=None, help="각 split 앞에서 N건만")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    runner = run_experiment2a if args.mode == "2a" else run_experiment2b

    summaries, mismatch_rows = {}, []
    with (args.out / "per_case.jsonl").open("w", encoding="utf-8") as jf:
        for split in args.splits:
            path = DATA / f"PersonaGuard_exp2_{split}.csv"
            cases = load_dataset(path)
            if args.limit:
                cases = cases[: args.limit]
            print(f"[{split}] {len(cases)}문항 실행 중...", flush=True)

            summary = runner(cases)
            d = summary.as_dict()
            for r in d.pop("results"):
                jf.write(json.dumps({"split": split, **r}, ensure_ascii=False) + "\n")
            summaries[split] = d
            print("  " + json.dumps(d, ensure_ascii=False), flush=True)

            for (etype, gold_action, expected, actual), n in sorted(action_mismatch(cases).items()):
                mismatch_rows.append({
                    "split": split, "entity_type": etype, "gold_action": gold_action,
                    "expected_policy_action": expected, "personaguard_policy_action": actual,
                    "count": n,
                })

    (args.out / "summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = ["split", "n_cases", "leakage_rate", "over_masking_rate", "action_accuracy",
              "format_accuracy", "consistency_violation_count"]
    with (args.out / "summary.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for split, d in summaries.items():
            w.writerow({"split": split, **{k: d[k] for k in fields[1:]}})

    with (args.out / "action_mismatch.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["split", "entity_type", "gold_action",
                                          "expected_policy_action", "personaguard_policy_action", "count"])
        w.writeheader()
        w.writerows(mismatch_rows)

    print(f"\n[완료] {args.out}")


if __name__ == "__main__":
    main()