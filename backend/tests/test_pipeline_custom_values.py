"""
run_rewrite()의 custom_values(Extension "직접 수정" 기능) 파라미터 단위 테스트.

test_pipeline.py와 동일한 이유로 exaone/ollama 호출은 mock으로 대체한다 — 여기서는
그 파일을 건드리지 않고 이 테스트에 필요한 mock만 별도로 구성한다.
"""

from unittest.mock import patch

import pytest

from app import pipeline, session_store


@pytest.fixture(autouse=True)
def _clean_session_store():
    yield
    session_store._store.clear()


@pytest.fixture(autouse=True)
def _mock_rewrite_llm_calls(monkeypatch):
    monkeypatch.setattr(pipeline, "polish_with_llm", lambda text: text)
    monkeypatch.setattr(pipeline, "self_check_rewrite", lambda text: None)
    monkeypatch.setattr(pipeline, "infer_purpose", lambda text: "")
    monkeypatch.setattr(pipeline, "classify_necessity", lambda purpose, entities: {})


def test_run_rewrite_uses_custom_value_for_protected_entity():
    prompt = "성신여자대학교 학생인데 교수님한테 이메일 좀 써줘"
    llm_raw = {"PERSON": [], "ADDRESS": [], "ORGANIZATION": [{"text": "성신여자대학교"}]}

    with patch("app.pipeline.detect_llm", return_value=llm_raw):
        result = pipeline.run_analysis(prompt)
    (session_id,) = session_store._store.keys()

    org_entity = next(e for e in result.entities if e.type == "ORGANIZATION")
    key = f"{org_entity.type}:{org_entity.start}:{org_entity.end}"

    rewritten = pipeline.run_rewrite(session_id, {key: True}, {key: "OO대학교"})

    assert "OO대학교" in rewritten
    assert "성신여자대학교" not in rewritten


def test_run_rewrite_ignores_custom_value_for_tier1_entity():
    prompt = "주민번호는 900101-1234567 입니다"

    with patch("app.pipeline.detect_llm", return_value={}):
        result = pipeline.run_analysis(prompt)
    (session_id,) = session_store._store.keys()

    rrn_entity = next(e for e in result.entities if e.type == "RRN")
    key = f"{rrn_entity.type}:{rrn_entity.start}:{rrn_entity.end}"

    # Tier1은 custom_values로 원본 값을 그대로 넣으려 해도 무시하고 강제 마스킹해야 한다.
    rewritten = pipeline.run_rewrite(session_id, {key: False}, {key: "900101-1234567"})

    assert "900101-1234567" not in rewritten


def test_run_rewrite_works_without_custom_values_argument():
    prompt = "이민수입니다"
    llm_raw = {"PERSON": [{"text": "이민수"}], "ADDRESS": [], "ORGANIZATION": []}

    with patch("app.pipeline.detect_llm", return_value=llm_raw):
        result = pipeline.run_analysis(prompt)
    (session_id,) = session_store._store.keys()

    # 기존 2-인자 호출 방식(하위 호환)도 그대로 동작해야 한다.
    rewritten = pipeline.run_rewrite(session_id, {})

    assert "이민수" not in rewritten
