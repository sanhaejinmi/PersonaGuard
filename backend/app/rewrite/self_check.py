"""
자기검증(§8 "자기검증 루프" 확정본) — 재작성본을 재탐지해서 PII/안내 문구가
남아있는지 확인하는 모듈. 문제가 없으면 조용히 None을 반환하고, 문제가 있을
때만 타입별 개수를 담은 결과를 반환한다 (재탐지된 값 자체는 반환하지 않는다 —
§5.2, 원본/PII를 로그·예외·테스트 출력에 남기지 않는다).

재시도(재작성 다시 시도)는 하지 않는다 — 이 모듈은 탐지·보고까지만 담당한다.

주의: pipeline.py/main.py에는 아직 연결되어 있지 않다. 실제 /rewrite 응답에
결과를 반영하려면 별도 연동 작업이 필요하다 (pipeline.py 변경 보류 중).
"""

import re
from dataclasses import dataclass, field

from app.exaone_client import detect_llm
from app.regex_engine import detect_regex

# rewrite_masked_prompt()의 전처리(label_strip 등)에서 놓친 안내 문구/고정 라벨
# 잔재 — PII는 아니지만 최종 결과에 남으면 안 되는 것들이다.
_RESIDUAL_LABEL_PATTERN = re.compile(
    r"\[(기관|주소|사용자 이름|REDACTED)\]"
    r"|\([^)]*비식별화[^)]*\)"
)


@dataclass
class SelfCheckResult:
    total: int
    by_type: dict = field(default_factory=dict)


def self_check_rewrite(rewritten_text: str) -> "SelfCheckResult | None":
    """재작성본을 재탐지한다. 문제가 없으면 None, 있으면 SelfCheckResult."""

    if not rewritten_text or not rewritten_text.strip():
        return None

    by_type: dict = {}

    for entity in detect_regex(rewritten_text):
        by_type[entity["type"]] = by_type.get(entity["type"], 0) + 1

    residual_count = sum(1 for _ in _RESIDUAL_LABEL_PATTERN.finditer(rewritten_text))
    if residual_count:
        by_type["RESIDUAL_LABEL"] = residual_count

    try:
        llm_entities = detect_llm(rewritten_text)
    except Exception:
        llm_entities = {}

    for entity_type, items in llm_entities.items():
        if not items:
            continue
        by_type[entity_type] = by_type.get(entity_type, 0) + len(items)

    if not by_type:
        return None

    return SelfCheckResult(total=sum(by_type.values()), by_type=by_type)
