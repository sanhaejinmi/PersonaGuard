import re

# 비식별화 안내 문구 + 앞 항목명 + 뒤 조사 통째로 제거
# 예) "이메일은 (이메일 비식별화)이고" → 제거
# 예) "계좌번호는 (비식별화)인데" → 제거
#
# 주의: 뒤 조사/연결어는 반드시 "긴 것부터" 한 그룹의 알터네이션으로 묶는다.
# 예전에는 단일조사(이가을를은는)와 연결어(이고|이며|...)를 별개의 optional
# 그룹 두 개로 나눠뒀는데, "이고"의 "이"가 단일조사 그룹에도 걸리는 바람에
# 그리디 매칭이 "이"만 먼저 먹어버리고 "고"가 그대로 남는 버그가 있었다
# (예: "이메일은 (이메일 비식별화)이고 팀장님한테" → "이메일은 고 팀장님한테").
_PII_LABEL_PATTERN = re.compile(
    r"[가-힣A-Za-z0-9]+[은는이가을를도]?\s*"
    r"\([^)]*비식별화[^)]*\)"
    r"(?:이고|이며|이라|인데|이야|입니다|이었|가|을|를|은|는|이)?"
    r"\s*[,\s]*"
)

# 잔여 안내 문구 제거 (앞 항목명 없이 남은 경우) — 위와 동일한 순서 규칙 적용.
_PII_RESIDUAL_PATTERN = re.compile(
    r"\([^)]*비식별화[^)]*\)"
    r"(?:이고|이며|이라|인데|이야|입니다|가|을|를|은|는|로|이)?"
    r"\s*[,\s]*"
)


def strip_disclosure_labels(text: str) -> str:
    """'(OO 비식별화)' 형태의 안내 문구를, 앞의 항목명(있으면)까지 통째로 제거한다.

    contact_label.normalize_contact_labels()와 org_address_label.normalize_org_address_labels()가
    만들어내는 "(연락처 비식별화)", "(이메일 비식별화)", "(기관 비식별화)", "(주소 비식별화)" 등이
    모두 이 공통 포맷을 쓰기 때문에, 타입별 모듈이 늘어나도 이 함수 하나로 처리된다.

    주의: `_PII_LABEL_PATTERN`은 안내 문구 바로 앞의 한국어 단어를 "항목명"이라고
    가정하고 함께 지운다 (예: "전화번호는 (연락처 비식별화)이고" → 통째로 제거).
    orchestrator.py(기존 타입 기반 흐름)처럼 masking이 항상 "항목명 + 안내 문구"
    형태를 만드는 경우에만 안전하다 — purpose_flow.py처럼 안내 문구 앞에 임의의
    문맥(예: "학생인데")이 올 수 있는 경우에는 그 문맥까지 같이 삭제될 위험이
    있으니 대신 `strip_residual_disclosure_phrase()`만 써야 한다.
    """
    text = _PII_LABEL_PATTERN.sub("", text)
    text = _PII_RESIDUAL_PATTERN.sub("", text)
    return text


def strip_residual_disclosure_phrase(text: str) -> str:
    """'(OO 비식별화)' 안내 문구 자체와 그 바로 뒤 조사·연결어만 제거한다.

    `strip_disclosure_labels()`와 달리 안내 문구 앞의 단어는 절대 건드리지
    않는다 — 앞에 어떤 문맥이 오든 안전하게 쓸 수 있다 (purpose_flow.py 참고).
    """
    return _PII_RESIDUAL_PATTERN.sub("", text)


# RRN/PASSPORT/DRIVER_LICENSE/FOREIGNER_REGISTRATION/BUSINESS_NUMBER/
# BANK_ACCOUNT/CARD 라벨. 이 타입들은 LLM(polish_with_llm)에 넘기면 "~는
# 비식별화되었습니다"처럼 안내 문구를 설명하는 새 문장으로 바꿔버리는 사례가
# 50개 프롬프트 실험에서 반복 재현됐다 — 괄호 자체가 사라져서 사후 정규식
# 안전망(strip_residual_disclosure_phrase)으로도 못 잡는다. 그래서 이 타입들의
# 라벨은 LLM에 보이기 전에 기계적으로 먼저 지운다(§3.1 Tier1/2 — 판단 여지가
# 없는 타입이라 LLM 판단 자체가 필요 없다).
_MECHANICAL_ONLY_LABELS = (
    "계좌번호", "카드번호", "주민번호", "여권번호",
    "운전면허번호", "외국인등록번호", "사업자등록번호", "개인정보",
)

_MECHANICAL_LABEL_PATTERN = re.compile(
    r"\((?:" + "|".join(_MECHANICAL_ONLY_LABELS) + r") 비식별화\)"
    r"(?:이고|이며|이라|인데|이야|입니다|가|을|를|은|는|로|이)?"
    r"\s*[,\s]*"
)


def strip_mechanical_only_labels(text: str) -> str:
    """판단 여지 없이 항상 삭제되는 타입(§3.1 Tier1/2)의 라벨을 LLM 없이
    기계적으로 지운다. 안내 문구 앞의 항목명(예: '운전면허번호는')은 건드리지
    않으므로 가끔 그 단어만 덩그러니 남을 수 있지만, LLM이 문장을 통째로
    다시 쓰다가 드리프트하는 것보다 훨씬 예측 가능하고 안전하다."""
    return _MECHANICAL_LABEL_PATTERN.sub("", text)


def cleanup_whitespace(text: str) -> str:
    """마스킹 잔재(별표), 문장 앞 쉼표, 중복 공백, 빈 괄호를 정리한다."""

    # 남은 별표 제거 (이름 마스킹 잔재)
    text = re.sub(r"\*+", "", text)

    # 문장 앞 쉼표/공백 정리
    text = re.sub(r"^\s*[,，]\s*", "", text)

    # 연속 공백 정리
    text = re.sub(r" {2,}", " ", text)

    # 빈 괄호 제거
    text = re.sub(r"\( *\)", "", text)

    return text.strip()
