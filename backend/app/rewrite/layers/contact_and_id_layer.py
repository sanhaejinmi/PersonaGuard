"""연락처/식별번호(전화, 이메일, 계좌, 카드, 주민번호 등) 레이어.

PERSON/ORGANIZATION/ADDRESS 레이어와 달리 LLM을 쓰지 않는다 — 이 타입들은
regex로 정확한 값·위치를 이미 알고 있고, action.py의 정책상 필요성과 무관하게
항상 삭제 대상이라 판단의 여지가 없다(§3.1 Tier1/2). 그래서 안내 문구로
기계적으로 치환하기만 하면 되고, 그 안내 문구를 자연스럽게 흡수하는 일은
뒤이은 person/organization/address 레이어(각자의 LLM 호출)가 "문장의 다른
부분은 그대로 유지"하면서 자연스럽게 처리해준다.
"""

_DELETE_LABELS = {
    "PHONE": "(연락처 비식별화)",
    "EMAIL": "(이메일 비식별화)",
    "BANK_ACCOUNT": "(계좌번호 비식별화)",
    "CARD": "(카드번호 비식별화)",
    "RRN": "(주민번호 비식별화)",
    "PASSPORT": "(여권번호 비식별화)",
    "DRIVER_LICENSE": "(운전면허번호 비식별화)",
    "FOREIGNER_REGISTRATION": "(외국인등록번호 비식별화)",
    "BUSINESS_NUMBER": "(사업자등록번호 비식별화)",
}
_DEFAULT_LABEL = "(개인정보 비식별화)"


def rewrite_contact_and_id_layer(text: str, entities: list) -> str:
    """entities: [{"type": str, "value": str}, ...] (regex 탐지분 — PERSON/ORG/ADDRESS 제외)."""
    for entity in entities:
        value = entity["value"]
        if value in text:
            label = _DELETE_LABELS.get(entity["type"], _DEFAULT_LABEL)
            text = text.replace(value, label)
    return text
