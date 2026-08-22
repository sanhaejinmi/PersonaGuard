"""
실험 2 — 개인정보 가리개 놀이 (§7) 에서 공용으로 쓰는 마스킹/치환 및 채점 로직.

apply_oracle_masking()은 app.pipeline._replacement_for()와 같은 정책 조합
(POLICY + mask_value + mask_person + replace_*)을 독립적으로 재구성한 것이다.
pipeline.py의 private 함수를 직접 가져오지 않고 이 파일에서 따로 구성했다 —
POLICY/mask_value/replace_*가 바뀌면 이 파일도 pipeline.py와 함께 확인해야
한다 (CLAUDE.md §2 AI Layer "Masking" 절과 동일한 제약).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.actions.masking import mask_value
from app.actions.policy import POLICY
from app.replace.replace_address import replace_address
from app.replace.replace_bank_account import replace_account
from app.replace.replace_email import replace_email
from app.replace.replace_organization import replace_organization
from app.replace.replace_phone import replace_phone
from experiments.dataset import GoldEntity

# 사람이 라벨링한 "정답 처리 방법"(§5) → PersonaGuard POLICY 액션. PersonaGuard는
# "delete"(완전 삭제)를 별도로 구현하지 않고 mask로 흡수하므로 delete==mask로 매핑한다.
GOLD_ACTION_TO_POLICY_ACTION = {
    "delete": "mask",
    "mask": "mask",
    "generalize": "replace",
    "keep": "keep",
}


def _mask_person(name: str) -> str:
    if len(name) <= 1:
        return "*"
    return name[0] + "*" * (len(name) - 1)


def replacement_for(entity_type: str, value: str) -> str:
    """POLICY 기준 실제 치환값. app.pipeline._replacement_for()와 동일 로직."""
    action = POLICY.get(entity_type, "mask")

    if action == "mask":
        if entity_type == "PERSON":
            return _mask_person(value)
        return mask_value(value, entity_type)

    if action == "replace":
        if entity_type == "PHONE":
            return replace_phone(value)
        if entity_type == "EMAIL":
            return replace_email(value)
        if entity_type == "BANK_ACCOUNT":
            return replace_account(value)
        if entity_type == "ADDRESS":
            return replace_address(value)
        if entity_type == "ORGANIZATION":
            return replace_organization(value)
        return "[REDACTED]"

    return value


def apply_oracle_masking(
    text: str, gold_entities: list[GoldEntity]
) -> tuple[str, dict[str, str]]:
    """실험 2-A — 정답 span을 그대로 신뢰하고(탐지 오류 배제) 정책 기반 치환만 적용한다.
    gold action이 "keep"인 항목은 손대지 않는다."""
    to_apply = [g for g in gold_entities if g.action != "keep"]
    replacements: dict[str, str] = {}
    result = text
    for g in sorted(to_apply, key=lambda g: g.start, reverse=True):
        new_value = replacement_for(g.type, g.text)
        replacements[f"{g.type}:{g.start}:{g.end}"] = new_value
        result = result[: g.start] + new_value + result[g.end :]
    return result, replacements


# 타입별 치환 결과 형식 점검(§7 "바꾼 형태가 맞는지"). mask_value()가 정형 출력을
# 내는 타입만 정규식으로 엄격히 검증하고, 자연어 치환(EMAIL/ADDRESS/ORGANIZATION)은
# 도메인이 매번 랜덤이거나 문장 구조가 다양해 고정 정규식으로 판단하기 어려워
# 느슨한 휴리스틱만 쓴다 — 필요하면 팀이 보강할 것 (§12 규칙7과 동일하게, 지금
# 실험이 아니라 다음 버전에서 보강 대상으로 남겨둔다).
_FORMAT_CHECKS: dict[str, re.Pattern] = {
    "RRN": re.compile(r"^\d{6}-\d\*{6}$"),
    "FOREIGNER_REGISTRATION": re.compile(r"^\d{6}-\d\*{6}$"),
    "PHONE": re.compile(r"^\d{3}-\d{2}\*\*-\*{4}$"),
    "DRIVER_LICENSE": re.compile(r"^\d{2}-\d{2}-X{6}-XX$"),
    "BUSINESS_NUMBER": re.compile(r"^\d{3}-\d{2}-X{5}$"),
    "CARD": re.compile(r"^\d+-X{4}-X{4}-\d+$"),
    "PASSPORT": re.compile(r"^\*+$"),
    "PERSON": re.compile(r"^.\*+$|^\*$"),
}


def check_format(entity_type: str, replaced_value: str, original_value: str) -> bool | None:
    """형식이 맞는지 확인한다. 판단 기준이 없는 타입(EMAIL/ADDRESS/ORGANIZATION 등)은
    None(판단 불가)을 돌려주고 — 최소한 원문과 달라졌는지만 별도로 확인해야 한다."""
    pattern = _FORMAT_CHECKS.get(entity_type)
    if pattern is None:
        return None
    return bool(pattern.match(replaced_value)) and replaced_value != original_value


def evaluate_leakage_and_overmask(
    gold_entities: list[GoldEntity], output_text: str
) -> tuple[list[dict], list[dict]]:
    """§7 "남아있는 개인정보 비율" / "너무 많이 지운 비율".

    치환/재작성 후 텍스트에 정답 값의 원문(literal)이 그대로 남아있는지로 판단한다
    — LLM 재작성(⑧)이 문장을 크게 바꾸면 의역으로 인한 오탐(실제로는 안전한데
    비슷한 표현이 남아 "leaked"로 잘못 잡히는 경우)이 있을 수 있어, 자동채점의
    한계로 문서화해둔다. 사람 검수 시 이 목록을 1차 후보로만 쓸 것.
    """
    leaked = []
    over_masked = []
    for g in gold_entities:
        present = g.text in output_text
        should_remain = g.action == "keep"
        if should_remain and not present:
            over_masked.append({"type": g.type, "text": g.text})
        if not should_remain and present:
            leaked.append({"type": g.type, "text": g.text})
    return leaked, over_masked


def evaluate_action_accuracy(gold_entities: list[GoldEntity]) -> tuple[int, int]:
    """§7 "처리 방법이 맞았는지" — PersonaGuard의 POLICY가 실제로 고르는 액션(mask/replace/keep)이
    사람이 정한 정답 처리 방법과 같은 "부류"인지 비교한다. (correct, total) 개수를 반환한다."""
    correct = 0
    total = 0
    for g in gold_entities:
        total += 1
        expected_policy_action = GOLD_ACTION_TO_POLICY_ACTION[g.action]
        if expected_policy_action == "keep":
            actual_policy_action = "keep"
        else:
            actual_policy_action = POLICY.get(g.type, "mask")
        if actual_policy_action == expected_policy_action:
            correct += 1
    return correct, total


def evaluate_consistency(gold_entities: list[GoldEntity], v1_prompt: str, output_text: str) -> list[dict]:
    """§7 "한결같이 처리했는지" — 같은 값이 문장에 여러 번 등장하면 매번 빠짐없이
    처리했는지 확인한다. action이 "keep"이 아닌데 원문 값 일부만 남아있으면 위반이다."""
    violations = []
    seen_values = set()
    for g in gold_entities:
        if g.action == "keep" or g.text in seen_values:
            continue
        seen_values.add(g.text)
        occurrences_in_source = v1_prompt.count(g.text)
        if occurrences_in_source <= 1:
            continue
        remaining = output_text.count(g.text)
        if remaining > 0:
            violations.append(
                {
                    "type": g.type,
                    "text": g.text,
                    "occurrences_in_source": occurrences_in_source,
                    "remaining_in_output": remaining,
                }
            )
    return violations


@dataclass
class MaskingResult:
    case_id: str
    output_text: str
    leaked: list[dict] = field(default_factory=list)
    over_masked: list[dict] = field(default_factory=list)
    action_correct: int = 0
    action_total: int = 0
    format_correct: int = 0
    format_checked: int = 0
    consistency_violations: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "output_text": self.output_text,
            "leaked": self.leaked,
            "over_masked": self.over_masked,
            "action_correct": self.action_correct,
            "action_total": self.action_total,
            "format_correct": self.format_correct,
            "format_checked": self.format_checked,
            "consistency_violations": self.consistency_violations,
        }
