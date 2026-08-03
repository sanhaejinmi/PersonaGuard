"""
실험 3 — 가린 뒤에도 원래 질문이 통하는지 (§8).

V1(원본) / V2(단순 가리기) / V3(PersonaGuard 재작성)를 만들고, 같은 answer_fn으로
R1/R2/R3(답변)을 받는다. app.pipeline.run_analysis()/run_rewrite()는 읽기 전용으로
호출만 한다.

채점은 두 단계로 나뉜다:
1. 자동 유사도(참고용 보조 지표) — 사람/블라인드 AI 채점 이전에 대략적인 방향을 보는 용도.
2. build_blind_grading_sheet() — §8 "공정하게 채점하는 방법"(라벨 숨기기 + 순서 섞기)에
   맞춘 실제 루브릭(1~5점 4개 항목 + 개인정보 통과/부분통과/실패) 채점용 시트.
   이 시트가 실제 점수를 매기는 부분이며, 사람 또는 별도의 블라인드 LLM 채점자가 채운다.
"""

from __future__ import annotations

import difflib
import random
from dataclasses import asdict, dataclass
from typing import Callable

from app.pipeline import run_analysis, run_rewrite
from experiments.dataset import TestCase
from experiments.masking_eval import apply_oracle_masking

AnswerFn = Callable[[str], str]

# §8 루브릭 4항목(1~5점) + 개인정보 보호 여부(별도 pass/partial/fail)
RUBRIC_AXES = ("purpose_preserved", "necessary_info_kept", "usefulness", "naturalness")
PRIVACY_VERDICTS = ("pass", "partial", "fail")


def stub_answer_fn(prompt: str) -> str:
    """오프라인 스모크테스트용 더미 답변자. 실제 실험 3 채점에는 쓰지 말 것 —
    하네스(파이프라인 연결, 시트 생성 등)가 제대로 도는지만 확인하는 용도다."""
    return f"[STUB ANSWER] {prompt[:120]}"


def ollama_answer_fn(model: str = "exaone3.5:7.8b") -> AnswerFn:
    """실제 채점용 답변자. 로컬 Ollama 서버 + 지정한 모델이 필요하다.
    §8이 확정한 tier1 판단용 모델(exaone3.5:2.4b)이 아니라, 실험 3은 "ChatGPT에
    보내는 상황"을 흉내내는 것이므로 별도로 모델을 지정할 수 있게 했다."""
    import ollama

    def _fn(prompt: str) -> str:
        response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
        return response["message"]["content"]

    return _fn


def build_v2(case: TestCase) -> str:
    """V2 — 정답 span 기준 단순 마스킹만 적용, 재작성 없음(§1)."""
    text, _ = apply_oracle_masking(case.v1_prompt, case.gold_entities)
    return text


def build_v3(case: TestCase) -> str:
    """V3 — PersonaGuard 전체 파이프라인(탐지 + 협상 기본값 + EEVE 재작성, §3)."""
    analysis = run_analysis(case.v1_prompt)
    return run_rewrite(analysis.session_id, decisions={})


def _similarity(a: str, b: str) -> float:
    """자동 유사도(참고용 보조 지표). 사람/블라인드 채점을 대신하지 않는다."""
    return difflib.SequenceMatcher(None, a, b).ratio()


@dataclass
class Experiment3Item:
    case_id: str
    v1: str
    v2: str
    v3: str
    r1: str
    r2: str
    r3: str
    similarity_v1_v2: float
    similarity_v1_v3: float
    similarity_r1_r2: float
    similarity_r1_r3: float


def run_experiment3(cases: list[TestCase], answer_fn: AnswerFn) -> list[Experiment3Item]:
    items = []
    for case in cases:
        v1 = case.v1_prompt
        v2 = build_v2(case)
        v3 = build_v3(case)
        r1, r2, r3 = answer_fn(v1), answer_fn(v2), answer_fn(v3)
        items.append(
            Experiment3Item(
                case_id=case.id,
                v1=v1,
                v2=v2,
                v3=v3,
                r1=r1,
                r2=r2,
                r3=r3,
                similarity_v1_v2=_similarity(v1, v2),
                similarity_v1_v3=_similarity(v1, v3),
                similarity_r1_r2=_similarity(r1, r2),
                similarity_r1_r3=_similarity(r1, r3),
            )
        )
    return items


def build_blind_grading_sheet(
    items: list[Experiment3Item], seed: int | None = None
) -> tuple[list[dict], dict[str, dict[str, str]]]:
    """§8 "공정하게 채점하는 방법" — 채점자에게는 라벨 없이(answer_a/b/c) 순서를 매
    케이스마다 무작위로 섞어서 보여준다.

    반환:
      grader_sheet — 채점자에게 그대로 전달하는 시트 (V1/V2/V3 라벨 없음, 채점 칸은 빈 값)
      answer_key   — case_id별 {"answer_a": "V1", ...} 매핑. 채점 중에는 공개하지 않고,
                      채점이 끝난 뒤 resolve_blind_scores()에만 사용한다.
    """
    rng = random.Random(seed)
    grader_sheet: list[dict] = []
    answer_key: dict[str, dict[str, str]] = {}
    slots = ("answer_a", "answer_b", "answer_c")

    for it in items:
        labeled = [("V1", it.r1), ("V2", it.r2), ("V3", it.r3)]
        rng.shuffle(labeled)

        row: dict = {"case_id": it.case_id}
        key: dict[str, str] = {}
        for slot, (true_label, text) in zip(slots, labeled):
            row[slot] = text
            key[slot] = true_label
            for axis in RUBRIC_AXES:
                row[f"{slot}_{axis}"] = None  # 채점자가 1~5점으로 채울 칸
            row[f"{slot}_privacy"] = None  # 채점자가 pass/partial/fail로 채울 칸

        grader_sheet.append(row)
        answer_key[it.case_id] = key

    return grader_sheet, answer_key


def resolve_blind_scores(graded_sheet: list[dict], answer_key: dict[str, dict[str, str]]) -> list[dict]:
    """채점이 끝난 시트를 answer_key로 되돌려 V1/V2/V3 기준 결과표로 정리한다."""
    resolved = []
    for row in graded_sheet:
        case_id = row["case_id"]
        key = answer_key[case_id]
        out: dict = {"case_id": case_id}
        for slot, true_label in key.items():
            out[f"{true_label}_privacy"] = row.get(f"{slot}_privacy")
            for axis in RUBRIC_AXES:
                out[f"{true_label}_{axis}"] = row.get(f"{slot}_{axis}")
        resolved.append(out)
    return resolved


def items_to_dicts(items: list[Experiment3Item]) -> list[dict]:
    return [asdict(it) for it in items]
