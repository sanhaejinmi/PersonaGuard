"""2-B 변형 — 사용자가 탐지된 항목을 전부 마스킹 선택한 경우.

experiment2.run_experiment2b()는 decisions={}로 호출해서 각 항목의 AI 기본
제안(default_masked)을 따른다. 그래서 남은 누출이 "탐지 실패" 때문인지
"탐지했지만 AI가 목적상 필요하다고 보아 기본 유지" 때문인지 구분되지 않는다.
여기서는 decisions를 전부 True로 채워 기본값 판단을 배제하고 탐지 실패분만 남긴다.
두 결과의 차이가 곧 협상 기본값이 책임지는 몫이다.

실행:
    python -m experiments.run_exp2_all --splits dev val --out experiments\\out\\exp2b_all
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.dataset import load_dataset
from experiments.experiment2 import _summarize
from experiments.masking_eval import (
    MaskingResult,
    evaluate_action_accuracy,
    evaluate_consistency,
    evaluate_leakage_and_overmask,
)
from app.pipeline import run_analysis, run_rewrite

DATA = Path("experiments/data")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--splits", nargs="+", default=["dev"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    summaries = {}
    with (args.out / "per_case.jsonl").open("w", encoding="utf-8") as jf:
        for split in args.splits:
            cases = load_dataset(DATA / f"PersonaGuard_exp2_{split}.csv")
            if args.limit:
                cases = cases[: args.limit]
            print(f"[{split}] {len(cases)}문항 실행 중...", flush=True)

            per_case = []
            for case in cases:
                analysis = run_analysis(case.v1_prompt)
                decisions = {f"{e.type}:{e.start}:{e.end}": True for e in analysis.entities}
                rewritten = run_rewrite(analysis.session_id, decisions=decisions)

                leaked, over_masked = evaluate_leakage_and_overmask(case.gold_entities, rewritten)
                ac, at = evaluate_action_accuracy(case.gold_entities)
                cons = evaluate_consistency(case.gold_entities, case.v1_prompt, rewritten)
                per_case.append(MaskingResult(
                    case_id=case.id, output_text=rewritten,
                    leaked=leaked, over_masked=over_masked,
                    action_correct=ac, action_total=at,
                    format_correct=0, format_checked=0,
                    consistency_violations=cons,
                ))

            d = _summarize("2-B(all)", cases, per_case).as_dict()
            for r in d.pop("results"):
                jf.write(json.dumps({"split": split, **r}, ensure_ascii=False) + "\n")
            summaries[split] = d
            print("  " + json.dumps(d, ensure_ascii=False), flush=True)

    (args.out / "summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[완료] {args.out}")


if __name__ == "__main__":
    main()