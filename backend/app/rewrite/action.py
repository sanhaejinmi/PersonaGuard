"""STEP4 — 엔티티 타입 + 필요성(STEP2-3 결과)을 기준으로 행동을 결정한다.

독립 모듈이다 — pipeline.py/main.py에는 연결되어 있지 않다 (purpose_flow.py 참고).
CLAUDE.md §3.1의 POLICY(mask/replace)와는 별개다 — 여기서는 "필요성"이라는
문맥 판단이 추가로 들어간다는 게 차이점이다.
"""

# 필요성과 무관하게 항상 이름 자체를 지우고 일반화하는 타입
_ALWAYS_GENERALIZE = {"PERSON"}

# 필요성과 무관하게 항상 삭제하는 타입 — 목적 달성에 리터럴 값이 쓰일 일이 없는
# 순수 식별·연락 정보 (학번은 아직 별도 탐지기가 없어 타입 문자열만 지원한다).
_ALWAYS_DELETE = {
    "PHONE",
    "EMAIL",
    "BANK_ACCOUNT",
    "CARD",
    "RRN",
    "PASSPORT",
    "DRIVER_LICENSE",
    "FOREIGNER_REGISTRATION",
    "BUSINESS_NUMBER",
    "STUDENT_ID",
}

# 필요성에 따라 유지/삭제를 판단하는 타입 ("학교명 → 유지 여부 판단")
_JUDGE_BY_NECESSITY = {"ORGANIZATION", "ADDRESS"}


def decide_action(entity_type: str, necessary: bool) -> str:
    """반환값: "keep" | "generalize" | "delete" """

    if entity_type in _ALWAYS_GENERALIZE:
        return "generalize"

    if entity_type in _ALWAYS_DELETE:
        return "delete"

    if entity_type in _JUDGE_BY_NECESSITY:
        return "keep" if necessary else "delete"

    # 알려지지 않은 타입은 필요성 판단 결과를 그대로 따른다.
    return "keep" if necessary else "delete"
