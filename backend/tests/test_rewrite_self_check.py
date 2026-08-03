"""
app/rewrite/self_check.py 테스트 — §8 "자기검증 루프"를 재작성본 재탐지(전체
재탐지, 재시도 없음, 문제 있을 때만 결과 반환) 방식으로 구현한 모듈.

detect_llm은 로컬 Ollama 호출이라 CI/다른 팀원 환경에서도 돌아가도록 patch한다
(test_pipeline.py의 관례와 동일). detect_regex는 순수 정규식이라 그대로 돈다.
"""

from unittest.mock import patch

from app.rewrite.self_check import self_check_rewrite


def test_clean_text_returns_none():
    with patch("app.rewrite.self_check.detect_llm", return_value={}):
        result = self_check_rewrite("담당자한테 문의 이메일 작성해줘")

    assert result is None


def test_bracket_label_residue_detected():
    with patch("app.rewrite.self_check.detect_llm", return_value={}):
        result = self_check_rewrite("[기관] 소속인데 문의 이메일 작성해줘")

    assert result is not None
    assert result.by_type["RESIDUAL_LABEL"] == 1
    assert result.total == 1


def test_disclosure_phrase_residue_detected():
    with patch("app.rewrite.self_check.detect_llm", return_value={}):
        result = self_check_rewrite("(기관 비식별화) 소속인데 문의 이메일 작성해줘")

    assert result is not None
    assert result.by_type["RESIDUAL_LABEL"] == 1


def test_regex_detectable_pii_residue_detected():
    with patch("app.rewrite.self_check.detect_llm", return_value={}):
        result = self_check_rewrite("전화번호는 010-1234-5678입니다")

    assert result is not None
    assert result.by_type["PHONE"] == 1


def test_llm_detectable_pii_residue_detected():
    llm_raw = {"PERSON": [{"text": "홍길동", "start": 0, "end": 3}]}
    with patch("app.rewrite.self_check.detect_llm", return_value=llm_raw):
        result = self_check_rewrite("홍길동님께 문의드립니다")

    assert result is not None
    assert result.by_type["PERSON"] == 1


def test_multiple_residual_types_sum_into_total():
    llm_raw = {"PERSON": [{"text": "홍길동", "start": 0, "end": 3}]}
    with patch("app.rewrite.self_check.detect_llm", return_value=llm_raw):
        result = self_check_rewrite("[기관] 전화번호는 010-1234-5678입니다")

    assert result is not None
    assert result.by_type["RESIDUAL_LABEL"] == 1
    assert result.by_type["PHONE"] == 1
    assert result.by_type["PERSON"] == 1
    assert result.total == 3


def test_llm_detection_failure_does_not_crash():
    with patch("app.rewrite.self_check.detect_llm", side_effect=RuntimeError("no model")):
        result = self_check_rewrite("아무 문제 없는 문장")

    assert result is None
