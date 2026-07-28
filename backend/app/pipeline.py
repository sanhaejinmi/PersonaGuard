"""
Pipeline Controller — §3 파이프라인 순서 중 백엔드 담당 구간(②~⑥, ⑧)을 조율한다.
①⑦⑨는 Extension 담당.

regex_engine.detect_regex()는 이제 자체적으로 정규식 간 겹침을 정리해서 반환한다
(RRN 우선 처리 포함). eeve_client.detect_llm()도 이제 start/end를 직접 계산해서
주지만, 그 오프셋은 detect_llm()에 넘긴 텍스트(마스킹본) 기준이라 원본 프롬프트
오프셋과 좌표계가 다르다 — 그래서 이 파일은 여전히 값(value)을 원본 프롬프트에서
재검색해 오프셋을 구한다.

app.actions.apply_policy.apply_policy()가 탐지+정책+치환을 한 번에 처리하는
자체 파이프라인을 이미 갖고 있지만, 텍스트 전체에 정책(POLICY)을 무조건 적용할
뿐 사용자의 항목별 결정(decisions)을 반영할 방법이 없다. 그래서 여기서는
apply_policy()를 통째로 쓰지 않고, 그 안에 있는 것과 동일한 정책(POLICY +
mask_value + replace_*)을 항목 단위로 재사용해 사용자 결정을 반영할 수 있게
만든다 — POLICY나 replace_* 쪽이 바뀌면 이 파일의 `_replacement_for()`도 같이
맞춰야 한다.
"""

import re
import uuid

from app import session_store
from app.actions.masking import mask_value
from app.actions.policy import POLICY
from app.exaone_client import detect_llm
from app.regex_engine import detect_regex
from app.replace.replace_bank_account import replace_account
from app.replace.replace_email import replace_email
from app.replace.replace_phone import replace_phone
from app.schemas import AnalyzeResponse, Entity

MAX_PROMPT_LENGTH = 50_000  # §5.5 ReDoS 방지 — 입력 길이 상한

# §3.1 — type 문자열 → tier 매핑 (regex 탐지분)
TIER1_TYPES = {"RRN", "PASSPORT", "DRIVER_LICENSE", "FOREIGNER_REGISTRATION"}
# 나머지 regex 타입(PHONE, EMAIL, BANK_ACCOUNT, CARD, BUSINESS_NUMBER 등)은 Tier2

# eeve_client.detect_llm()이 실제로 반환하는 카테고리 (§4.2 — life_context/question_essential
# 구분은 아직 미구현이라, LLM 탐지분은 전부 Tier3로 취급한다)
LLM_CATEGORIES = ("PERSON", "ADDRESS", "ORGANIZATION")


def _tier_of(entity_type: str, source: str) -> int:
    if source == "regex":
        return 1 if entity_type in TIER1_TYPES else 2
    return 3


def _replacement_for(entity_type: str, value: str) -> str:
    """app.actions.apply_policy.apply_policy()와 동일한 POLICY를 항목 단위로 재사용."""
    action = POLICY.get(entity_type, "mask")

    if action == "mask":
        return mask_value(value, entity_type)

    if action == "replace":
        if entity_type == "PHONE":
            return replace_phone(value)
        if entity_type == "EMAIL":
            return replace_email(value)
        if entity_type == "BANK_ACCOUNT":
            return replace_account(value)
        if entity_type == "PERSON":
            return "[사용자 이름]"
        if entity_type == "ADDRESS":
            return "[주소]"
        if entity_type == "ORGANIZATION":
            return "[기관]"
        return "[REDACTED]"

    return value


def _find_all(text: str, value: str) -> list[tuple[int, int]]:
    if not value:
        return []
    return [(m.start(), m.end()) for m in re.finditer(re.escape(value), text)]


def _llm_items(prompt: str, llm_raw: dict) -> list[dict]:
    """detect_llm() 출력을 원본 프롬프트 기준 오프셋으로 변환.
    detect_llm()이 주는 start/end는 자신에게 입력된 텍스트(마스킹본) 기준이라
    원본 프롬프트 좌표계와 달라서 쓰지 않고, 값(text)을 원본에서 재검색한다."""
    items = []
    for category in LLM_CATEGORIES:
        for entry in llm_raw.get(category, []):
            value = entry.get("text", "")
            for start, end in _find_all(prompt, value):
                items.append(
                    {
                        "type": category,
                        "value": value,
                        "start": start,
                        "end": end,
                        "tier": _tier_of(category, "eeve"),
                    }
                )
    return items


def _dedupe_overlaps(items: list[dict]) -> list[dict]:
    """§3 ⑤ 통합 — 키 충돌(겹치는 span) 정리.

    regex_engine.detect_regex()가 정규식 간 겹침은 이미 정리해서 주지만, regex
    탐지분과 LLM 탐지분 사이에 겹치는 경우까지는 처리하지 않으므로 여기서 한 번
    더 정리한다. 더 넓은 span을 우선하고, 넓이가 같으면 먼저 탐지된 항목을 우선한다.
    """
    ordered = sorted(items, key=lambda e: (e["start"], -(e["end"] - e["start"])))
    accepted: list[dict] = []
    for e in ordered:
        if any(e["start"] < a["end"] and e["end"] > a["start"] for a in accepted):
            continue
        accepted.append(e)
    return sorted(accepted, key=lambda e: e["start"])


def _apply_replacements(text: str, items: list[dict]) -> str:
    """§4.4 — 오프셋 역순으로 치환."""
    for e in sorted(items, key=lambda e: e["start"], reverse=True):
        text = text[: e["start"]] + _replacement_for(e["type"], e["value"]) + text[e["end"] :]
    return text


def run_analysis(prompt: str) -> AnalyzeResponse:
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise ValueError(f"prompt exceeds max length ({MAX_PROMPT_LENGTH})")

    # ② Regex Detection (regex_engine이 자체적으로 겹침도 정리해서 반환)
    regex_entities = detect_regex(prompt)
    regex_items = [{**e, "tier": _tier_of(e["type"], "regex")} for e in regex_entities]

    # ③ Masking — EEVE 입력은 반드시 마스킹본이어야 한다 (§5.1 불변조건)
    regex_masked = _apply_replacements(prompt, regex_items) if regex_items else prompt

    # ④ EEVE 1차 호출(탐색) — 실제 로컬 LLM 호출
    llm_raw = detect_llm(regex_masked)
    llm_items = _llm_items(prompt, llm_raw)

    # ⑤ Detection Result 통합 (원본 오프셋 기준, 겹침 정리)
    items = _dedupe_overlaps(regex_items + llm_items)

    # 기본 정책 적용본 (POLICY 기준 mask/replace)
    final_masked = _apply_replacements(prompt, items)

    entities = [
        Entity(type=e["type"], value=e["value"], start=e["start"], end=e["end"], tier=e["tier"])
        for e in items
    ]
    # entities와 동일 index로 매칭되는 치환 미리보기 (Extension 협상 화면 "AI 제안")
    candidates = [_replacement_for(e["type"], e["value"]) for e in items]

    session_id = str(uuid.uuid4())
    session_store.create(session_id, original=prompt, items=items)

    return AnalyzeResponse(
        session_id=session_id,
        original=prompt,
        masked=final_masked,
        entities=entities,
        candidates=candidates,
    )


def run_rewrite(session_id: str, decisions: dict[str, bool]) -> str:
    """
    ⑧ 재작성. decisions 키는 "TYPE:start:end" (Extension approval_sender.js와 동일 규약).
    미언급 항목의 기본값은 보호(True) — approval_sender.js와 동일.

    Tier1(고유식별정보)은 decisions에 뭐라고 오든 항상 보호한다 — Extension도
    동일하게 강제하지만, 서버도 이중으로 강제한다 (§5 — 클라이언트만 신뢰하지 않는다).
    """
    session = session_store.get(session_id)
    if session is None:
        raise KeyError(f"unknown or expired session_id: {session_id}")

    items = session["items"]

    def _key(e: dict) -> str:
        return f"{e['type']}:{e['start']}:{e['end']}"

    to_protect = [e for e in items if e["tier"] == 1 or decisions.get(_key(e), True)]

    return _apply_replacements(session["original"], to_protect)
