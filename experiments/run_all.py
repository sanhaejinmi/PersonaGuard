"""
실험 실행 CLI — "PersonaGuard 실험 계획" 문서의 실험 1·2·3을 한 번에 또는 개별로 실행한다.

사용 예 (PersonaGuard 레포 루트에서 실행, 즉 `python -m experiments.run_all ...`).
experiments/는 backend/와 형제 폴더지만, app 패키지(backend/app)는
experiments/__init__.py가 sys.path에 backend/를 등록해줘서 실행 위치와
무관하게 import된다:

  # 하네스 로직만 스모크테스트 (Ollama 불필요, 정규식 베이스라인만 실행)
  python -m experiments.run_all --dataset experiments/sample_dataset.json --experiment 1 --detectors rule1,rule2

  # 실험 1 전체 (rule1/rule2/personaguard 비교) — 로컬 Ollama 필요
  python -m experiments.run_all --dataset experiments/sample_dataset.json --experiment 1

  # 실험 2-A (탐지 오류 배제, 마스킹 로직만 채점) — Ollama 불필요
  python -m experiments.run_all --dataset experiments/sample_dataset.json --experiment 2a

  # 실험 2-B (전체 파이프라인) — 로컬 Ollama 필요
  python -m experiments.run_all --dataset experiments/sample_dataset.json --experiment 2b

  # 실험 3 (V3 생성은 파이프라인을 타므로 Ollama 필요, R1/R2/R3만 스텁 답변자로 대체)
  python -m experiments.run_all --dataset experiments/sample_dataset.json --experiment 3 --answer-fn stub

주의: 실험 1의 personaguard 탐지기, 2-B, 3은 모두 app.pipeline(run_analysis/
run_rewrite)을 거치므로 로컬 Ollama 서버(+exaone3.5:2.4b, polish용 7.8b)가
필요하다. --answer-fn stub은 실험 3에서 "AI에게 질문해서 답변 받기" 단계만
대체할 뿐, V2/V3를 만드는 단계(마스킹/재작성)는 대체하지 않는다 — V2는
Ollama가 필요 없지만 V3는 여전히 필요하다.
Ollama 없이 하네스 로직만 점검하려면 --detectors rule1,rule2 / --experiment 2a
조합을 쓴다(이 둘은 app.pipeline을 호출하지 않는다).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass  # 콘솔이 reconfigure를 지원하지 않는 환경(일부 IDE 등) — 출력이 깨져도 실행 자체는 계속된다

from experiments.baselines import keyword_list_detector, personaguard_detector, regex_only_detector
from experiments.dataset import filter_cases, load_dataset, validate_split_isolation
from experiments.experiment1 import run_experiment1
from experiments.experiment2 import run_experiment2a, run_experiment2b
from experiments.experiment3 import (
    build_blind_grading_sheet,
    items_to_dicts,
    ollama_answer_fn,
    run_experiment3,
    stub_answer_fn,
)
from experiments.report import (
    experiment1_by_risk_table,
    experiment1_by_type_table,
    experiment1_summary_table,
    experiment2_summary_table,
    write_csv,
    write_json,
)

ALL_DETECTORS = {
    "rule1": ("rule1_regex_only", regex_only_detector),
    "rule2": ("rule2_keyword_list", keyword_list_detector),
    "personaguard": ("personaguard", personaguard_detector),
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--dataset", required=True, help="TestCase JSON 경로")
    parser.add_argument(
        "--experiment", choices=["1", "2a", "2b", "3", "all"], default="all"
    )
    parser.add_argument("--split", choices=["dev", "val", "test", "challenge"], default=None)
    parser.add_argument("--domain", default=None)
    parser.add_argument("--out", default="experiments/out")
    parser.add_argument(
        "--detectors",
        default="rule1,rule2,personaguard",
        help="실험 1에서 비교할 탐지기 (rule1,rule2,personaguard 중 콤마로 선택)",
    )
    parser.add_argument("--answer-fn", choices=["stub", "ollama"], default="stub")
    parser.add_argument("--answer-model", default="exaone3.5:7.8b")
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    cases = load_dataset(args.dataset)
    for warning in validate_split_isolation(cases):
        print(f"[WARN] {warning}")

    cases = filter_cases(cases, split=args.split, domain=args.domain)
    if not cases:
        raise SystemExit("선택한 조건(--split/--domain)에 해당하는 테스트 케이스가 없습니다.")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[정보] {len(cases)}개 케이스 로드 완료 → {out_dir}")

    if args.experiment in ("1", "all"):
        selected = [k.strip() for k in args.detectors.split(",") if k.strip()]
        detectors = {ALL_DETECTORS[k][0]: ALL_DETECTORS[k][1] for k in selected}
        results = run_experiment1(cases, detectors, iou_threshold=args.iou_threshold)
        write_json({k: v.as_dict() for k, v in results.items()}, out_dir / "experiment1_full.json")
        write_csv(experiment1_summary_table(results), out_dir / "experiment1_summary.csv")
        write_csv(experiment1_by_type_table(results), out_dir / "experiment1_by_type.csv")
        write_csv(experiment1_by_risk_table(results), out_dir / "experiment1_by_risk.csv")
        print("[실험 1] 완료 →", out_dir / "experiment1_summary.csv")

    summaries = []
    if args.experiment in ("2a", "all"):
        summary_2a = run_experiment2a(cases)
        write_json(summary_2a.as_dict(), out_dir / "experiment2a_full.json")
        summaries.append(summary_2a)
        print("[실험 2-A] 완료 — leakage_rate=%.4f, over_masking_rate=%.4f" % (
            summary_2a.leakage_rate, summary_2a.over_masking_rate
        ))

    if args.experiment in ("2b", "all"):
        summary_2b = run_experiment2b(cases)
        write_json(summary_2b.as_dict(), out_dir / "experiment2b_full.json")
        summaries.append(summary_2b)
        print("[실험 2-B] 완료 — leakage_rate=%.4f, over_masking_rate=%.4f" % (
            summary_2b.leakage_rate, summary_2b.over_masking_rate
        ))

    if summaries:
        write_csv(experiment2_summary_table(summaries), out_dir / "experiment2_summary.csv")

    if args.experiment in ("3", "all"):
        answer_fn = stub_answer_fn if args.answer_fn == "stub" else ollama_answer_fn(args.answer_model)
        items = run_experiment3(cases, answer_fn)
        write_json(items_to_dicts(items), out_dir / "experiment3_items.json")

        grader_sheet, answer_key = build_blind_grading_sheet(items, seed=args.seed)
        write_json(grader_sheet, out_dir / "experiment3_grading_sheet.json")
        write_json(answer_key, out_dir / "experiment3_answer_key.json")  # 채점 끝나기 전엔 채점자에게 공개 금지
        print(
            "[실험 3] 완료 —",
            out_dir / "experiment3_grading_sheet.json",
            "(채점용, 라벨 숨김) /",
            out_dir / "experiment3_answer_key.json",
            "(채점 후 복원용, 비공개)",
        )
        if args.answer_fn == "stub":
            print("[안내] --answer-fn stub은 하네스 점검용입니다. 실제 채점에는 --answer-fn ollama를 쓰세요.")


if __name__ == "__main__":
    main()
