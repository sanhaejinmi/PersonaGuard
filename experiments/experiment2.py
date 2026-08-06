"""
실험 2 — 개인정보 가리개 놀이 (§7).

- 실험 2-A: 정답 span을 그대로 주고(탐지 오류 배제) 가리는 실력만 본다.
- 실험 2-B: PersonaGuard가 스스로 찾고 스스로 가리는 전체 파이프라인(§3 ②~⑧)을 그대로 본다.
  app.pipeline.run_analysis()/run_rewrite()는 읽기 전용으로 호출만 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.pipeline import run_analysis, run_rewrite
from experiments.dataset import TestCase
from experiments.masking_eval import (
    MaskingResult,
    apply_oracle_masking,
    evaluate_action_accuracy,
    evaluate_consistency,
    evaluate_leakage_and_overmask,
    check_format,
)


@dataclass
class Experiment2Summary:
    mode: str  # "2-A" / "2-B"
    n_cases: int
    leakage_rate: float  # 지웠어야 하는데 남은 비율 (전체 gold entity 중)
    over_masking_rate: float  # 지우면 안 되는데 지운 비율
    action_accuracy: float
    format_accuracy: float | None  # 형식 판단 가능한 항목이 없으면 None
    consistency_violation_count: int
    results: list[MaskingResult] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "n_cases": self.n_cases,
            "leakage_rate": round(self.leakage_rate, 4),
            "over_masking_rate": round(self.over_masking_rate, 4),
            "action_accuracy": round(self.action_accuracy, 4),
            "format_accuracy": round(self.format_accuracy, 4) if self.format_accuracy is not None else None,
            "consistency_violation_count": self.consistency_violation_count,
            "results": [r.as_dict() for r in self.results],
        }


def _summarize(mode: str, cases: list[TestCase], per_case_results: list[MaskingResult]) -> Experiment2Summary:
    total_gold = sum(len(c.gold_entities) for c in cases)
    total_leaked = sum(len(r.leaked) for r in per_case_results)
    total_over_masked = sum(len(r.over_masked) for r in per_case_results)
    total_action_correct = sum(r.action_correct for r in per_case_results)
    total_action_total = sum(r.action_total for r in per_case_results)
    total_format_correct = sum(r.format_correct for r in per_case_results)
    total_format_checked = sum(r.format_checked for r in per_case_results)
    total_consistency_violations = sum(len(r.consistency_violations) for r in per_case_results)

    return Experiment2Summary(
        mode=mode,
        n_cases=len(cases),
        leakage_rate=total_leaked / total_gold if total_gold else 0.0,
        over_masking_rate=total_over_masked / total_gold if total_gold else 0.0,
        action_accuracy=total_action_correct / total_action_total if total_action_total else 0.0,
        format_accuracy=(total_format_correct / total_format_checked) if total_format_checked else None,
        consistency_violation_count=total_consistency_violations,
        results=per_case_results,
    )


def run_experiment2a(cases: list[TestCase]) -> Experiment2Summary:
    """정답 span이 주어졌다고 가정하고 마스킹/치환 로직만 평가한다 (탐지 오류 배제)."""
    per_case: list[MaskingResult] = []

    for case in cases:
        output_text, replacements = apply_oracle_masking(case.v1_prompt, case.gold_entities)
        leaked, over_masked = evaluate_leakage_and_overmask(case.gold_entities, output_text)
        action_correct, action_total = evaluate_action_accuracy(case.gold_entities)
        consistency_violations = evaluate_consistency(case.gold_entities, case.v1_prompt, output_text)

        format_correct = format_checked = 0
        for g in case.gold_entities:
            key = f"{g.type}:{g.start}:{g.end}"
            if g.action == "keep" or key not in replacements:
                continue
            verdict = check_format(g.type, replacements[key], g.text)
            if verdict is None:
                continue
            format_checked += 1
            if verdict:
                format_correct += 1

        per_case.append(
            MaskingResult(
                case_id=case.id,
                output_text=output_text,
                leaked=leaked,
                over_masked=over_masked,
                action_correct=action_correct,
                action_total=action_total,
                format_correct=format_correct,
                format_checked=format_checked,
                consistency_violations=consistency_violations,
            )
        )

    return _summarize("2-A", cases, per_case)


def run_experiment2b(cases: list[TestCase]) -> Experiment2Summary:
    """PersonaGuard 전체 파이프라인(탐지 → 협상 기본값 → 재작성)을 그대로 실행해 평가한다.
    로컬 Ollama 서버(+exaone3.5:2.4b, polish용 7.8b)가 필요하다."""
    per_case: list[MaskingResult] = []

    for case in cases:
        analysis = run_analysis(case.v1_prompt)
        rewritten = run_rewrite(analysis.session_id, decisions={})

        leaked, over_masked = evaluate_leakage_and_overmask(case.gold_entities, rewritten)
        action_correct, action_total = evaluate_action_accuracy(case.gold_entities)
        consistency_violations = evaluate_consistency(case.gold_entities, case.v1_prompt, rewritten)

        per_case.append(
            MaskingResult(
                case_id=case.id,
                output_text=rewritten,
                leaked=leaked,
                over_masked=over_masked,
                action_correct=action_correct,
                action_total=action_total,
                format_correct=0,
                format_checked=0,  # ⑧ 재작성 후 문장이 자연어로 다듬어져 정형 포맷 검사가 의미 없음
                consistency_violations=consistency_violations,
            )
        )

    return _summarize("2-B", cases, per_case)
