import re

# ORGANIZATION/ADDRESS 정책("replace")이 만들어내는 고정 라벨.
# apply_policy.py 쪽은 replace_organization()/replace_address()로 일반화된 표현을
# 만들지만, pipeline.py._replacement_for()는 이 고정 라벨을 그대로 텍스트에 남긴다.
_ORG_PLACEHOLDER_PATTERN = re.compile(r"\[기관\]")
_ADDRESS_PLACEHOLDER_PATTERN = re.compile(r"\[주소\]")


def normalize_org_address_labels(text: str) -> str:
    """'[기관]'/'[주소]' 고정 라벨을 공통 안내 문구 포맷으로 바꾼다.

    이 변환이 없으면 '[기관]', '[주소]' 문자열이 재작성 결과에 그대로 노출된다
    (기관/주소 언급이 필요한 항목이 아니라, 문장에서 통째로 제거되어야 하는
    항목이기 때문 — contact_label.normalize_contact_labels()와 동일하게 처리).
    이후 label_strip.strip_disclosure_labels()가 앞의 항목명까지 함께 제거한다.
    """
    text = _ORG_PLACEHOLDER_PATTERN.sub("(기관 비식별화)", text)
    text = _ADDRESS_PLACEHOLDER_PATTERN.sub("(주소 비식별화)", text)
    return text
