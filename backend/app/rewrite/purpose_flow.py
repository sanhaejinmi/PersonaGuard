"""사용자가 제안한 STEP1-5 "목적 보존 재작성" 흐름의 독립 구현체.

STEP1 목적 파악 → STEP2-3 필요/불필요 정보 판단 → STEP4 타입별 행동 결정 →
STEP5 새 문장 생성(목적을 컨텍스트로 함께 전달).

설계는 승인됐지만(2026-07-29), pipeline.py/main.py에는 아직 연결되어 있지 않다
— apply_policy.py와 같은 위치의, 실제 /analyze·/rewrite 경로와는 별개인 독립
파이프라인이다. 실서비스에 반영하려면 pipeline.py 쪽 연동이 별도로 필요하다.

2026-07-29 재구조화 시도 및 롤백: person/organization/address를 각각 독립
LLM 호출(app/rewrite/layers/)로 체이닝하는 구조를 시도했으나, exaone3.5:2.4b
(2.4B, 작은 모델)로 실제 로컬 테스트해보니 호출을 체이닝할수록 드리프트가
누적되어 "~써줘" 같은 요청문을 "~해드리겠습니다" 같은 응답문으로 바꾸거나
없던 직함을 지어내는 등 프롬프트를 강화해도 재현되는 심각한 문제가 있었다.
그래서 STEP5는 다시 단일 `llm_polish.polish_with_llm()` 호출로 되돌렸다 —
대신 STEP1에서 구한 purpose를 컨텍스트로 함께 넘겨서(§ llm_polish.py 규칙 11),
"목적을 재작성 단계까지 가져가면 더 정확해질 것"이라는 원래 의도는 최소
변경으로 살렸다. `app/rewrite/layers/`는 코드 자체는 남겨뒀지만 이 흐름에서는
쓰지 않는다.

detect_regex/exaone_client.detect_llm은 §5.1 불변조건대로, 정형 PII를 마스킹한
텍스트만 LLM에 넘긴 뒤 호출한다 — pipeline.py와 동일한 순서를 따른다.
"""

import re
from dataclasses import dataclass, field

from app.exaone_client import detect_llm
from app.regex_engine import detect_regex
from app.rewrite.action import decide_action
from app.rewrite.entity_filter import is_valid_organization, is_valid_person_name
from app.rewrite.label_strip import (
    cleanup_whitespace,
    strip_mechanical_only_labels,
    strip_residual_disclosure_phrase,
)
from app.rewrite.llm_polish import polish_with_llm
from app.rewrite.necessity import classify_necessity
from app.rewrite.person import strip_person_mentions
from app.rewrite.purpose import infer_purpose

_LLM_CATEGORIES = ("PERSON", "ADDRESS", "ORGANIZATION")

# "delete" 행동을 그냥 빈 문자열로 지우면 "번호는 이고 연락 가능합니다"처럼 앞뒤
# 서술이 붕 뜬 채로 남는다. 안내 문구 포맷으로 바꿔서 처리한다.
#
# PHONE/EMAIL/ORGANIZATION/ADDRESS는 라벨을 LLM(STEP5)에 그대로 넘긴다 — rule 4가
# "계좌번호는 (비식별화)인데"처럼 라벨과 그 앞 항목명이 같이 있을 때 그 항목명까지
# 안전하게 지워주는 걸 실제로 확인했다. 라벨을 여기서 먼저 지워버리면 LLM이 볼 수
# 있는 건 "계좌번호는"이라는 멀쩡해 보이는 문구뿐이라 지울 근거가 없어진다.
#
# 반면 BANK_ACCOUNT/CARD/RRN/PASSPORT/DRIVER_LICENSE/FOREIGNER_REGISTRATION/
# BUSINESS_NUMBER는 LLM에 넘기면 "~는 비식별화되었습니다"처럼 안내 문구를
# 설명하는 새 문장으로 바꿔버리는 사례가 50개 프롬프트 실험에서 반복 재현됐다
# (프롬프트에 정확히 일치하는 예시를 추가해도 고쳐지지 않음 — exaone3.5:2.4b의
# 한계로 보임). 그래서 이 타입들의 라벨은 아래에서 `strip_mechanical_only_labels()`로
# LLM을 거치지 않고 기계적으로 지운다 (§3.1 Tier1/2 — 판단 여지가 없는 타입이라
# LLM 판단 자체가 필요 없다).
#
# 주의: orchestrator.py의 `strip_disclosure_labels()`(정규식으로 앞 단어까지 지움)는
# 여기서 쓰지 않는다 — 안내 문구 앞에 "학생인데"처럼 무관한 문맥이 올 수 있는
# purpose_flow 특성상 그 문맥까지 같이 삭제되는 위험이 있다(실제로 발견된 버그).
_DELETE_LABELS = {
    "PHONE": "(연락처 비식별화)",
    "EMAIL": "(이메일 비식별화)",
    "ORGANIZATION": "(기관 비식별화)",
    "ADDRESS": "(주소 비식별화)",
    "BANK_ACCOUNT": "(계좌번호 비식별화)",
    "CARD": "(카드번호 비식별화)",
    "RRN": "(주민번호 비식별화)",
    "PASSPORT": "(여권번호 비식별화)",
    "DRIVER_LICENSE": "(운전면허번호 비식별화)",
    "FOREIGNER_REGISTRATION": "(외국인등록번호 비식별화)",
    "BUSINESS_NUMBER": "(사업자등록번호 비식별화)",
}
_DEFAULT_DELETE_LABEL = "(개인정보 비식별화)"


@dataclass
class EntityDecision:
    type: str
    value: str
    necessary: bool
    action: str  # "keep" | "generalize" | "delete"


@dataclass
class PurposeRewriteResult:
    purpose: str
    decisions: list = field(default_factory=list)
    rewritten: str = ""


def _mask_regex_entities(prompt: str, regex_entities: list) -> str:
    """§5.1 — EEVE(exaone) 탐색 입력은 반드시 마스킹본이어야 한다."""
    text = prompt
    for e in sorted(regex_entities, key=lambda e: e["start"], reverse=True):
        text = text[: e["start"]] + f"[{e['type']}]" + text[e["end"] :]
    return text


def _mask_all_entities(prompt: str, entities: list) -> str:
    """regex + LLM 탐지분을 전부 마스킹한 텍스트 — STEP1 목적 추론 전용.

    `masked_for_llm`(regex만 마스킹)을 그대로 STEP1에 넘겼더니, PERSON/
    ORGANIZATION/ADDRESS는 아직 원문 그대로 남아 있어서 목적 요약에 이름·
    기관명이 그대로 옮겨지고, 그 purpose 문자열이 다시 STEP5 컨텍스트로
    전달되면서 이미 제거했어야 할 PII가 최종 결과에 되돌아오는 사례가 실제로
    발견됐다(50개 실험 #12 — "신동엽 원장"이 purpose를 거쳐 최종 결과에 재노출).
    그래서 목적 추론만큼은 탐지된 엔티티를 전부 마스킹한 텍스트로 한다.
    """
    text = prompt
    for e in entities:
        if e["value"] in text:
            text = text.replace(e["value"], f"[{e['type']}]")
    return text


_BRACKET_PLACEHOLDER_PATTERN = re.compile(r"\[[^\[\]]{1,30}\]")


def _strip_bracket_placeholders(text: str) -> str:
    """'[ORGANIZATION]', '[본인 이름]', '[연락처]'류 대괄호 자리표시자를 지운다.

    두 가지 경로로 생긴다: (1) `_mask_all_entities()`가 붙인 내부용 타입
    토큰을 exaone이 purpose 요약에 그대로 옮기거나(구분 12 참고), 그 purpose가
    STEP5 컨텍스트로 넘어가면서 최종 결과에도 그대로 옮겨지는 경우, (2) 모델이
    이메일 "완성본"처럼 답변하면서 스스로 `[이름]`, `[연락처]` 같은 빈 칸을
    지어내는 경우. 어느 쪽이든 사용자에게 나가는 문장에 대괄호 자리표시자가
    남으면 안 되므로 purpose와 최종 rewritten 양쪽에 안전망으로 적용한다.
    """
    return _BRACKET_PLACEHOLDER_PATTERN.sub("", text)


def _collect_llm_entities(llm_raw: dict) -> list:
    """detect_llm() 결과를 모으되, exaone이 일반 명사·직함·숫자열을 PERSON/
    ORGANIZATION으로 오탐지하는 알려진 문제(§2)를 entity_filter로 걸러낸다."""

    entities = []
    for category in _LLM_CATEGORIES:
        for item in llm_raw.get(category, []):
            value = item["text"]
            if category == "PERSON" and not is_valid_person_name(value):
                continue
            if category == "ORGANIZATION" and not is_valid_organization(value):
                continue
            entities.append({"type": category, "value": value})
    return entities


def rewrite_with_purpose(prompt: str) -> PurposeRewriteResult:
    regex_entities = detect_regex(prompt)
    masked_for_llm = _mask_regex_entities(prompt, regex_entities)

    try:
        llm_raw = detect_llm(masked_for_llm)
    except Exception:
        llm_raw = {}

    entities = [
        {"type": e["type"], "value": e["value"]} for e in regex_entities
    ] + _collect_llm_entities(llm_raw)

    purpose = _strip_bracket_placeholders(infer_purpose(_mask_all_entities(prompt, entities)))
    necessity = classify_necessity(purpose, entities)

    decisions = []
    person_mask_info = []
    text = prompt

    for entity in entities:
        necessary = necessity.get(entity["value"], False)
        action = decide_action(entity["type"], necessary)
        decisions.append(
            EntityDecision(
                type=entity["type"],
                value=entity["value"],
                necessary=necessary,
                action=action,
            )
        )

        if action == "keep":
            continue

        if action == "generalize":
            # PERSON 전용 — person.py가 이름 + 뒤 조사를 함께 제거해준다.
            person_mask_info.append({"type": "PERSON", "original": entity["value"]})
            continue

        # action == "delete": 안내 문구로 바꿔서 llm_polish가 앞 항목명·뒤
        # 조사까지 통째로 제거하도록 한다 (값 기준 치환 — 같은 값이 여러 번
        # 등장하면 한 번에 함께 처리된다).
        if entity["value"] in text:
            label = _DELETE_LABELS.get(entity["type"], _DEFAULT_DELETE_LABEL)
            text = text.replace(entity["value"], label)

    text = strip_person_mentions(text, person_mask_info)

    # RRN/PASSPORT/DRIVER_LICENSE/FOREIGNER_REGISTRATION/BUSINESS_NUMBER/
    # BANK_ACCOUNT/CARD 라벨은 LLM에 넘기지 않고 여기서 기계적으로 지운다.
    # PHONE/EMAIL/ORGANIZATION/ADDRESS 라벨은 그대로 두고 LLM(STEP5)이 처리한다.
    text = strip_mechanical_only_labels(text)
    text = cleanup_whitespace(text)

    # STEP5 — 자연스러운 문장으로 다듬기 (목적을 컨텍스트로 함께 전달)
    rewritten = polish_with_llm(text, purpose=purpose) if text.strip() else text

    # 안전망 — LLM이 안내 문구를 못 지우고 그대로 남기는 경우가 실제로 있었다
    # (50개 실험에서 재현: 같은 입력도 매번 완벽하게 지우지는 못함). 앞 단어는
    # 건드리지 않는 안전한 잔여 제거만 한 번 더 적용해 최소한 "(...비식별화...)"
    # 원문이 그대로 노출되는 것만은 막는다.
    rewritten = strip_residual_disclosure_phrase(rewritten)
    rewritten = _strip_bracket_placeholders(rewritten)
    rewritten = cleanup_whitespace(rewritten)

    return PurposeRewriteResult(purpose=purpose, decisions=decisions, rewritten=rewritten)
