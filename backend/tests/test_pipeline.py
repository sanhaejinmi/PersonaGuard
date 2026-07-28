"""
pipeline.py 단위 테스트.

app.regex_engine.detect_regex는 실제(순수 정규식, 외부 의존성 없음) 그대로 돌린다.
app.exaone_client.detect_llm은 로컬 Ollama를 실제로 호출하므로, CI/다른 팀원 환경에
모델이 없어도 테스트가 돌아가도록 golden_cases.json에 미리 준비한 값으로
patch한다 — pipeline의 조율 로직(오프셋 병합·tier 분류·세션·rewrite 강제)만
검증하는 게 목적이다. 실제 Ollama 연동 자체를 확인하려면 이 파일이 아니라
서버를 직접 띄워서 확인해야 한다.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app import pipeline, session_store
from app.actions.masking import mask_value

FIXTURES = Path(__file__).parent / "fixtures" / "golden_cases.json"


def _load_cases() -> list[dict]:
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _clean_session_store():
    yield
    session_store._store.clear()


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["name"])
def test_run_analysis_matches_golden_case(case):
    with patch("app.pipeline.detect_llm", return_value=case["llm_raw"]):
        result = pipeline.run_analysis(case["prompt"])

    detected_types = {e.type for e in result.entities}
    assert detected_types == set(case["expected_types"])

    for entity in result.entities:
        assert entity.tier == case["expected_tiers"][entity.type]
        # 탐지된 원본 값이 마스킹본에 그대로 남아있으면 안 된다.
        assert entity.value not in result.masked

    assert len(result.candidates) == len(result.entities)
    assert result.session_id
    assert result.original == case["prompt"]


def test_run_analysis_rejects_overlong_prompt():
    with pytest.raises(ValueError):
        pipeline.run_analysis("가" * (pipeline.MAX_PROMPT_LENGTH + 1))


def test_run_analysis_creates_isolated_session():
    with patch("app.pipeline.detect_llm", return_value={}):
        pipeline.run_analysis("첫 번째 요청")
        pipeline.run_analysis("두 번째 요청")

    assert len(session_store._store) == 2


def test_run_rewrite_forces_tier1_mask_even_if_user_unchecks():
    prompt = "제 주민번호는 900101-1234567 입니다"
    with patch("app.pipeline.detect_llm", return_value={}):
        result = pipeline.run_analysis(prompt)
    (session_id,) = session_store._store.keys()

    entity = next(e for e in result.entities if e.type == "RRN")
    # 사용자가 원문 유지(False)를 선택해도 Tier1은 서버가 강제로 마스킹해야 한다.
    decisions = {f"{entity.type}:{entity.start}:{entity.end}": False}

    rewritten = pipeline.run_rewrite(session_id, decisions)

    assert "900101-1234567" not in rewritten
    assert mask_value("900101-1234567", "RRN") in rewritten


def test_run_rewrite_respects_user_decision_for_tier3():
    prompt = "이민수입니다"
    llm_raw = {"PERSON": [{"text": "이민수"}], "ADDRESS": [], "ORGANIZATION": []}
    with patch("app.pipeline.detect_llm", return_value=llm_raw):
        result = pipeline.run_analysis(prompt)
    (session_id,) = session_store._store.keys()

    entity = result.entities[0]
    # Tier3는 사용자가 원문 유지(False)를 선택하면 그대로 존중돼야 한다.
    decisions = {f"{entity.type}:{entity.start}:{entity.end}": False}

    rewritten = pipeline.run_rewrite(session_id, decisions)

    assert "이민수" in rewritten


def test_run_rewrite_unknown_session_raises():
    with pytest.raises(KeyError):
        pipeline.run_rewrite("does-not-exist", {})


def test_run_rewrite_can_be_called_repeatedly_for_same_session():
    # 재작성은 승인 전 미리보기라, Extension의 "다시 수정하기"가 결정을 바꿔서
    # 같은 session_id로 /rewrite를 여러 번 호출할 수 있어야 한다.
    prompt = "제 번호는 010-1234-5678입니다"
    with patch("app.pipeline.detect_llm", return_value={}):
        result = pipeline.run_analysis(prompt)
    (session_id,) = session_store._store.keys()

    entity = result.entities[0]
    key = f"{entity.type}:{entity.start}:{entity.end}"

    # PHONE은 POLICY상 "mask"라 mask_value()의 결정론적 부분 마스킹을 거친다.
    first = pipeline.run_rewrite(session_id, {key: True})
    assert "010-1234-5678" not in first
    assert mask_value("010-1234-5678", "PHONE") in first
    assert session_store.get(session_id) is not None  # 세션이 살아있어야 재호출 가능

    second = pipeline.run_rewrite(session_id, {key: False})
    assert "010-1234-5678" in second
