"""app/rewrite/label_strip.py 테스트 — 특히 strip_mechanical_only_labels()."""

from app.rewrite.label_strip import (
    strip_mechanical_only_labels,
    strip_residual_disclosure_phrase,
)


def test_strip_mechanical_only_labels_removes_rrn_label():
    text = "주민번호는 (주민번호 비식별화)인데 연말정산 서류 작성해줘"
    result = strip_mechanical_only_labels(text)
    assert "비식별화" not in result
    assert "연말정산 서류 작성해줘" in result


def test_strip_mechanical_only_labels_removes_all_seven_types():
    labels = [
        "(계좌번호 비식별화)", "(카드번호 비식별화)", "(주민번호 비식별화)",
        "(여권번호 비식별화)", "(운전면허번호 비식별화)",
        "(외국인등록번호 비식별화)", "(사업자등록번호 비식별화)",
    ]
    for label in labels:
        text = f"항목은 {label}인데 서류 작성해줘"
        result = strip_mechanical_only_labels(text)
        assert label not in result, f"failed for {label}"


def test_strip_mechanical_only_labels_leaves_contact_and_org_labels_untouched():
    """PHONE/EMAIL/ORGANIZATION/ADDRESS 라벨은 LLM(STEP5)이 처리해야 하므로
    여기서 건드리면 안 된다."""
    text = "(연락처 비식별화)로 문의 메일 좀 써줘"
    result = strip_mechanical_only_labels(text)
    assert result == text


def test_strip_residual_disclosure_phrase_still_catches_mechanical_labels_as_fallback():
    """혹시 기계적 제거를 건너뛰어도, 안전망(STEP5 이후)이 그물 역할을 한다."""
    text = "주민번호는 (주민번호 비식별화)인데 연말정산 서류 작성해줘"
    result = strip_residual_disclosure_phrase(text)
    assert "비식별화" not in result
