import re

# 전화번호: 010-23**-****
_PHONE_PATTERN = re.compile(r"\d{2,4}-\d{2,4}\*+-\*+")

# 이메일
_EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"
)


def normalize_contact_labels(text: str) -> str:
    """부분 마스킹된 전화번호/이메일을 공통 안내 문구 포맷으로 바꾼다.
    이후 label_strip.strip_disclosure_labels()가 항목명까지 함께 제거한다."""
    text = _PHONE_PATTERN.sub("(연락처 비식별화)", text)
    text = _EMAIL_PATTERN.sub("(이메일 비식별화)", text)
    return text
