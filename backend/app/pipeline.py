"""
Pipeline Controller — §3 파이프라인 순서 중 백엔드 담당 구간(②~⑥, ⑧)을 조율한다.
①⑦⑨는 Extension 담당.

regex_engine / masking / eeve_client / llm_masking_1은 팀원 구현이 실제로 붙어
있어서 그대로 호출한다. eeve_client.detect_llm()은 로컬 Ollama(exaone3.5:2.4b)를
실제로 호출하므로, Ollama가 떠 있고 모델이 pull되어 있어야 정상 동작한다.

replace_client.replace_personal_info()는 원본 전체를 LLM에 보내 가명으로
재작성하지만 함수 시그니처가 텍스트만 받아서, 사용자의 항목별 결정(decisions)을
반영할 방법이 없다. 그래서 run_rewrite()에서는 이 함수를 쓰지 않고, 확정
항목만 placeholder로 치환하는 결정론적 방식을 쓴다 — §3 ⑦→⑧ 요구사항
("확정 항목만 비식별화, 미선택 항목은 원문 유지")을 정확히 지키기 위함이다.
replace_client.py를 실제로 쓰려면 항목별 선택을 반영하도록 그쪽 인터페이스가
먼저 바뀌어야 한다 (별도 논의 필요, 지금은 미사용).
"""

import re
import uuid

from app import session_store
from app.eeve_client import detect_llm
from app.llm_masking_1 import mask_text
from app.masking import mask_prompt
from app.regex_engine import detect_regex
from app.schemas import AnalyzeResponse, Entity

MAX_PROMPT_LENGTH = 50_000  # §5.5 ReDoS 방지 — 입력 길이 상한

# §3.1 — type 문자열 → tier 매핑 (regex 탐지분)
TIER1_TYPES = {"RRN", "PASSPORT", "DRIVER_LICENSE"}
# 나머지 regex 타입(PHONE, EMAIL, BANK_ACCOUNT, CARD, BUSINESS_NUMBER 등)은 Tier2

# eeve_client.detect_llm()이 실제로 반환하는 카테고리 (§4.2 — life_context/question_essential
# 구분은 아직 미구현이라, LLM 탐지분은 전부 Tier3로 취급한다)
LLM_CATEGORIES = ("PERSON", "ADDRESS", "ORGANIZATION")


def _tier_of(entity_type: str, source: str) -> int:
    if source == "regex":
        return 1 if entity_type in TIER1_TYPES else 2
    return 3


def _find_all(text: str, value: str) -> list[tuple[int, int]]:
    if not value:
        return []
    return [(m.start(), m.end()) for m in re.finditer(re.escape(value), text)]


def _dedupe_overlaps(items: list[dict]) -> list[dict]:
    """§3 ⑤ 통합 — 키 충돌(겹치는 span) 정리.

    regex 하위 모듈들의 패턴이 서로 겹칠 수 있다 (예: 주민등록번호 안의 일부가
    사업자등록번호 패턴에도 매치됨). 겹치는 항목이 그대로 남으면 같은 값이
    두 번 표시되는 것은 물론, run_rewrite()의 오프셋 치환이 겹치는 두 span을
    각각 잘라내다 텍스트가 깨진다. 더 넓은 span을 우선하고, 넓이가 같으면
    먼저 탐지된 항목(= regex_engine 등록 순서)을 우선한다.
    """
    ordered = sorted(items, key=lambda e: (e["start"], -(e["end"] - e["start"])))
    accepted: list[dict] = []
    for e in ordered:
        if any(e["start"] < a["end"] and e["end"] > a["start"] for a in accepted):
            continue
        accepted.append(e)
    return sorted(accepted, key=lambda e: e["start"])


def _llm_items(prompt: str, llm_raw: dict) -> list[dict]:
    """detect_llm() 출력({"PERSON": [{"text": ...}], ...})을 오프셋 있는 항목으로 변환.
    LLM은 오프셋을 주지 않으므로 원본 프롬프트에서 값을 재검색한다."""
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


def run_analysis(prompt: str) -> AnalyzeResponse:
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise ValueError(f"prompt exceeds max length ({MAX_PROMPT_LENGTH})")

    # ② Regex Detection
    regex_entities = detect_regex(prompt)

    # ③ Masking — EEVE 입력은 반드시 마스킹본이어야 한다 (§5.1 불변조건)
    regex_masked = mask_prompt(prompt, regex_entities) if regex_entities else prompt

    # ④ EEVE 1차 호출(탐색) — 실제 로컬 LLM 호출
    llm_raw = detect_llm(regex_masked)

    # ⑤ Detection Result 통합 (원본 오프셋 기준)
    llm_items = _llm_items(prompt, llm_raw)
    regex_items = [
        {**e, "tier": _tier_of(e["type"], "regex")} for e in regex_entities
    ]
    items = _dedupe_overlaps(regex_items + llm_items)

    # 최종 마스킹본 (regex + eeve 탐지분 모두 반영)
    final_masked = mask_text(regex_masked, llm_raw)

    entities = [
        Entity(type=e["type"], value=e["value"], start=e["start"], end=e["end"], tier=e["tier"])
        for e in items
    ]
    # entities와 동일 index로 매칭되는 치환 미리보기 (Extension 협상 화면 "AI 제안")
    candidates = [f"[{e['type']}]" for e in items]

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

    Tier1(고유식별정보)은 decisions에 뭐라고 오든 항상 마스킹한다 — Extension도
    동일하게 강제하지만, 서버도 이중으로 강제한다 (§5 — 클라이언트만 신뢰하지 않는다).
    """
    session = session_store.get(session_id)
    if session is None:
        raise KeyError(f"unknown or expired session_id: {session_id}")

    items = session["items"]

    def _key(e: dict) -> str:
        return f"{e['type']}:{e['start']}:{e['end']}"

    to_mask = [e for e in items if e["tier"] == 1 or decisions.get(_key(e), True)]

    text = session["original"]
    for e in sorted(to_mask, key=lambda e: e["start"], reverse=True):
        text = text[: e["start"]] + f"[{e['type']}]" + text[e["end"] :]

    # 세션은 여기서 지우지 않는다 — Extension의 "다시 수정하기"가 같은 session_id로
    # /rewrite를 다시 호출할 수 있어야 한다 (재작성은 승인 전 미리보기 단계).
    # TTL·정리 정책은 §8 미확정.
    return text
