from app.rewrite.contact_label import normalize_contact_labels
from app.rewrite.label_strip import cleanup_whitespace, strip_disclosure_labels
from app.rewrite.llm_polish import polish_with_llm
from app.rewrite.org_address_label import normalize_org_address_labels
from app.rewrite.person import strip_person_mentions


def rewrite_masked_prompt(masked_text: str, mask_info: list) -> str:
    """⑧ EEVE 2차 호출(재작성) — 타입별 정리 모듈을 순서대로 적용한 뒤 LLM으로 다듬는다.

    1) person: 마스킹된/원본 이름 언급 제거
    2) contact_label: 부분마스킹된 전화번호/이메일 → 공통 안내 문구 포맷
    3) org_address_label: 고정 라벨 '[기관]'/'[주소]' → 공통 안내 문구 포맷
    4) label_strip: 안내 문구 + 앞 항목명을 문장에서 통째로 제거
    5) llm_polish: exaone3.5:2.4b로 최종 다듬기
    """

    if not masked_text or not masked_text.strip():
        return masked_text

    cleaned_text = strip_person_mentions(masked_text, mask_info)
    cleaned_text = normalize_contact_labels(cleaned_text)
    cleaned_text = normalize_org_address_labels(cleaned_text)
    cleaned_text = strip_disclosure_labels(cleaned_text)
    cleaned_text = cleanup_whitespace(cleaned_text)

    return polish_with_llm(cleaned_text)
