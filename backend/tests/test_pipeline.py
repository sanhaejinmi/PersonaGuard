"""
pipeline.py 단위 테스트.

app.regex_engine.detect_regex는 실제(순수 정규식, 외부 의존성 없음) 그대로 돌린다.
app.exaone_client.detect_llm, app.rewrite.llm_polish.polish_with_llm,
app.rewrite.self_check.self_check_rewrite, app.rewrite.purpose.infer_purpose,
app.rewrite.necessity.classify_necessity는 로컬 Ollama를 실제로 호출하므로(polish/
purpose/necessity는 exaone3.5:7.8b — 이 환경엔 없을 수 있음), CI/다른 팀원 환경에서도
돌아가도록 기본 mock으로 대체한다 — pipeline의 조율 로직(오프셋 병합·tier 분류·세션·
rewrite 강제·재시도·기본값 제안)만 검증하는 게 목적이다. 실제 Ollama 연동 자체를
확인하려면 이 파일이 아니라 서버를 직접 띄워서 확인해야 한다.
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


@pytest.fixture(autouse=True)
def _mock_rewrite_llm_calls(monkeypatch):
    """polish_with_llm은 기본적으로 입력을 그대로 통과, self_check_rewrite는
    기본적으로 '문제 없음'(None)으로 처리 — 재시도 관련 테스트에서만 개별 override.
    infer_purpose/classify_necessity는 판단 대상이 없다고(빈 결과) 처리 — 필요성
    관련 테스트에서만 개별 override."""
    monkeypatch.setattr(pipeline, "polish_with_llm", lambda text: text)
    monkeypatch.setattr(pipeline, "self_check_rewrite", lambda text: None)
    monkeypatch.setattr(pipeline, "infer_purpose", lambda text: "")
    monkeypatch.setattr(pipeline, "classify_necessity", lambda purpose, entities: {})


def test_default_masked_follows_necessity_for_address_and_organization(monkeypatch):
    prompt = "성신여자대학교 근처 맛집 추천해줘"
    llm_raw = {"PERSON": [], "ADDRESS": [], "ORGANIZATION": [{"text": "성신여자대학교"}]}
    monkeypatch.setattr(pipeline, "detect_llm", lambda text: llm_raw)
    monkeypatch.setattr(pipeline, "infer_purpose", lambda text: "근처 맛집 추천")
    monkeypatch.setattr(
        pipeline,
        "classify_necessity",
        lambda purpose, entities: {"성신여자대학교": True},
    )

    result = pipeline.run_analysis(prompt)

    org_entity = next(e for e in result.entities if e.type == "ORGANIZATION")
    assert org_entity.default_masked is False  # 목적상 필요하다고 판단 → 기본 유지 제안


def test_default_masked_masks_when_not_necessary(monkeypatch):
    prompt = "성신여자대학교 학생인데 교수님한테 이메일 좀 써줘"
    llm_raw = {"PERSON": [], "ADDRESS": [], "ORGANIZATION": [{"text": "성신여자대학교"}]}
    monkeypatch.setattr(pipeline, "detect_llm", lambda text: llm_raw)
    monkeypatch.setattr(pipeline, "infer_purpose", lambda text: "교수에게 이메일 작성")
    monkeypatch.setattr(
        pipeline,
        "classify_necessity",
        lambda purpose, entities: {"성신여자대학교": False},
    )

    result = pipeline.run_analysis(prompt)

    org_entity = next(e for e in result.entities if e.type == "ORGANIZATION")
    assert org_entity.default_masked is True  # 불필요 → 기본 마스킹 제안


def test_default_masked_ignores_necessity_for_always_masked_types(monkeypatch):
    # PERSON/PHONE 등은 action.py의 _ALWAYS_GENERALIZE/_ALWAYS_DELETE라 필요성과
    # 무관하게 항상 기본 마스킹이어야 한다 — necessity가 True라고 나와도 무시.
    prompt = "이민수이고 번호는 010-1234-5678입니다"
    llm_raw = {"PERSON": [{"text": "이민수"}], "ADDRESS": [], "ORGANIZATION": []}
    monkeypatch.setattr(pipeline, "detect_llm", lambda text: llm_raw)
    monkeypatch.setattr(pipeline, "infer_purpose", lambda text: "아무 목적")
    monkeypatch.setattr(
        pipeline, "classify_necessity", lambda purpose, entities: {"이민수": True}
    )

    result = pipeline.run_analysis(prompt)

    person_entity = next(e for e in result.entities if e.type == "PERSON")
    phone_entity = next(e for e in result.entities if e.type == "PHONE")
    assert person_entity.default_masked is True
    assert phone_entity.default_masked is True


def test_run_rewrite_uses_default_masked_when_decision_unspecified():
    prompt = "성신여자대학교 근처 맛집 추천해줘"
    llm_raw = {"PERSON": [], "ADDRESS": [], "ORGANIZATION": [{"text": "성신여자대학교"}]}
    with patch("app.pipeline.detect_llm", return_value=llm_raw), patch(
        "app.pipeline.infer_purpose", return_value="근처 맛집 추천"
    ), patch(
        "app.pipeline.classify_necessity",
        return_value={"성신여자대학교": True},
    ):
        result = pipeline.run_analysis(prompt)
    (session_id,) = session_store._store.keys()

    org_entity = next(e for e in result.entities if e.type == "ORGANIZATION")
    assert org_entity.default_masked is False

    # decisions에 이 항목을 아예 언급하지 않으면 default_masked(False)를 따라야
    # 하므로, 원문 그대로 남아있어야 한다.
    rewritten = pipeline.run_rewrite(session_id, {})
    assert "성신여자대학교" in rewritten


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


def test_run_rewrite_retries_once_when_self_check_flags_issue(monkeypatch):
    prompt = "이민수입니다"
    llm_raw = {"PERSON": [{"text": "이민수"}], "ADDRESS": [], "ORGANIZATION": []}
    with patch("app.pipeline.detect_llm", return_value=llm_raw):
        pipeline.run_analysis(prompt)
    (session_id,) = session_store._store.keys()

    polish_calls = []

    def fake_polish(text):
        polish_calls.append(text)
        return f"polished-{len(polish_calls)}"

    check_calls = []

    def fake_self_check(text):
        # 첫 번째 결과만 문제 있다고 보고, 재시도 결과는 깨끗하다고 처리.
        check_calls.append(text)
        return None if len(check_calls) > 1 else object()

    monkeypatch.setattr(pipeline, "polish_with_llm", fake_polish)
    monkeypatch.setattr(pipeline, "self_check_rewrite", fake_self_check)

    result = pipeline.run_rewrite(session_id, {})

    assert len(polish_calls) == 2  # 최초 1회 + 재시도 1회, 그 이상은 없음
    assert result == "polished-2"


def test_run_rewrite_gives_up_after_one_retry_if_still_flagged(monkeypatch):
    prompt = "이민수입니다"
    llm_raw = {"PERSON": [{"text": "이민수"}], "ADDRESS": [], "ORGANIZATION": []}
    with patch("app.pipeline.detect_llm", return_value=llm_raw):
        pipeline.run_analysis(prompt)
    (session_id,) = session_store._store.keys()

    polish_calls = []
    monkeypatch.setattr(pipeline, "polish_with_llm", lambda text: polish_calls.append(1) or "still-flagged")
    monkeypatch.setattr(pipeline, "self_check_rewrite", lambda text: object())  # 항상 문제 있음

    result = pipeline.run_rewrite(session_id, {})

    assert len(polish_calls) == 2  # 무한 재시도 아님 — 1회 재시도로 끝
    assert result == "still-flagged"  # 그래도 남아있으면 결과를 그대로 반환
