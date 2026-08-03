"""
app/rewrite/purpose.py, necessity.py, purpose_flow.py 테스트.

ollama 호출(purpose 추론, 필요성 판단, 최종 다듬기)은 로컬 모델 없이도 CI에서
돌아가도록 전부 patch한다. exaone_client.detect_llm도 마찬가지로 patch한다
(test_pipeline.py의 관례와 동일).
"""

from unittest.mock import patch

from app.rewrite.necessity import classify_necessity
from app.rewrite.purpose import infer_purpose
from app.rewrite.purpose_flow import rewrite_with_purpose


def _fake_chat(content: str):
    return {"message": {"content": content}}


def test_infer_purpose_parses_json_response():
    with patch("app.rewrite.purpose.ollama.chat") as mock_chat:
        mock_chat.return_value = _fake_chat('{"purpose": "교수님께 결석 사실을 알리는 이메일 작성"}')
        purpose = infer_purpose("아무 문장")

    assert purpose == "교수님께 결석 사실을 알리는 이메일 작성"


def test_infer_purpose_returns_empty_string_on_failure():
    with patch("app.rewrite.purpose.ollama.chat", side_effect=RuntimeError("no model")):
        purpose = infer_purpose("아무 문장")

    assert purpose == ""


def test_classify_necessity_parses_json_response():
    entities = [
        {"type": "PERSON", "value": "김철수"},
        {"type": "ORGANIZATION", "value": "성신여자대학교"},
    ]
    with patch("app.rewrite.necessity.ollama.chat") as mock_chat:
        mock_chat.return_value = _fake_chat(
            '{"김철수": false, "성신여자대학교": true}'
        )
        result = classify_necessity("교수님께 결석 사실을 알리는 이메일 작성", entities)

    assert result == {"김철수": False, "성신여자대학교": True}


def test_classify_necessity_defaults_to_unnecessary_on_failure():
    entities = [{"type": "PERSON", "value": "김철수"}]
    with patch("app.rewrite.necessity.ollama.chat", side_effect=RuntimeError("no model")):
        result = classify_necessity("아무 목적", entities)

    assert result == {"김철수": False}


def test_rewrite_with_purpose_end_to_end():
    """purpose.py/necessity.py와 layers/* 는 전부 `import ollama`로 같은 모듈
    객체를 공유하므로, 모듈별 경로로 따로 patch하면 서로 덮어써 버린다. 대신
    system prompt 내용으로 어떤 호출인지 구분하는 side_effect 하나로 patch한다."""

    prompt = "김철수입니다, 성신여자대학교 학생인데 010-1234-5678로 연락 가능합니다. 교수님한테 결석계 이메일 좀 써줘"

    def _fake_ollama_chat(model, messages, options=None):
        system_content = messages[0]["content"]
        if "목적을 한 문장으로 요약" in system_content:
            return _fake_chat('{"purpose": "교수님께 결석 사실을 알리는 이메일 작성"}')
        if "필요한 정보인지 판단" in system_content:
            return _fake_chat(
                '{"김철수": false, "성신여자대학교": true, "010-1234-5678": false}'
            )
        if "사람 이름" in system_content:
            return _fake_chat(
                "성신여자대학교 학생인데 (연락처 비식별화)로 연락 가능합니다. 교수님한테 결석계 이메일 좀 써줘"
            )
        if "기관/소속" in system_content:
            return _fake_chat(
                "성신여자대학교 학생인데 (연락처 비식별화)로 연락 가능합니다. 교수님한테 결석계 이메일 좀 써줘"
            )
        return _fake_chat("성신여자대학교 학생인데 교수님한테 결석계 이메일 좀 작성해줘")

    with patch("app.rewrite.purpose_flow.detect_llm") as mock_detect_llm, \
         patch("ollama.chat", side_effect=_fake_ollama_chat):

        mock_detect_llm.return_value = {
            "PERSON": [{"text": "김철수"}],
            "ADDRESS": [],
            "ORGANIZATION": [{"text": "성신여자대학교"}],
        }

        result = rewrite_with_purpose(prompt)

    assert result.purpose == "교수님께 결석 사실을 알리는 이메일 작성"

    by_type = {d.type: d for d in result.decisions}
    assert by_type["PERSON"].action == "generalize"
    assert by_type["PHONE"].action == "delete"
    assert by_type["ORGANIZATION"].action == "keep"

    assert "김철수" not in result.rewritten
    assert "010-1234-5678" not in result.rewritten
    # address 레이어는 항목이 없으면 호출 자체가 안 되므로 통과 텍스트 그대로 유지되고,
    # 마지막 안전망이 person/organization 레이어가 못 지운 안내 문구를 정리한다.
    assert "비식별화" not in result.rewritten


def test_purpose_inference_never_sees_llm_detected_pii():
    """회귀 테스트 — 50개 실험 #12에서 발견된 버그.

    예전에는 STEP1(infer_purpose)에 regex 탐지분만 마스킹한 텍스트를 넘겨서,
    LLM 탐지분(PERSON/ORGANIZATION/ADDRESS)은 원문 그대로 노출됐다. exaone이
    이걸 그대로 옮겨 목적 문자열에 이름을 포함시키고("병원 홈페이지에
    신동엽 원장의 공지사항 초안 작성"), 그 purpose가 다시 STEP5 컨텍스트로
    전달되면서 이미 제거했어야 할 이름이 최종 결과에 재노출됐다. 지금은
    entities(regex+LLM)를 전부 마스킹한 텍스트를 STEP1에 넘겨야 한다.
    """

    prompt = "저는 신동엽 원장입니다, 병원 홈페이지 공지사항 초안 써줘"
    captured_purpose_user_prompt = {}

    def _fake_ollama_chat(model, messages, options=None):
        system_content = messages[0]["content"]
        if "목적을 한 문장으로 요약" in system_content:
            captured_purpose_user_prompt["content"] = messages[1]["content"]
            return _fake_chat('{"purpose": "병원 홈페이지 공지사항 초안 작성"}')
        if "필요한 정보인지 판단" in system_content:
            return _fake_chat('{"신동엽 원장": false, "병원": true}')
        return _fake_chat("병원 홈페이지 공지사항 초안 작성해줘")

    with patch("app.rewrite.purpose_flow.detect_llm") as mock_detect_llm, \
         patch("ollama.chat", side_effect=_fake_ollama_chat):

        mock_detect_llm.return_value = {
            "PERSON": [{"text": "신동엽 원장"}],
            "ADDRESS": [],
            "ORGANIZATION": [{"text": "병원"}],
        }

        result = rewrite_with_purpose(prompt)

    assert "신동엽 원장" not in captured_purpose_user_prompt["content"]
    assert "신동엽 원장" not in result.purpose
    assert "신동엽 원장" not in result.rewritten


def test_bracket_placeholder_tokens_stripped_from_purpose_and_output():
    """회귀 테스트 — 이름 유출은 막았지만, exaone이 내부용 '[ORGANIZATION]'
    타입 토큰이나 스스로 지어낸 '[본인 이름]' 같은 자리표시자를 purpose나
    최종 결과에 그대로 남기는 사례가 실제로 나왔다. 양쪽 다 안전망으로
    대괄호 자리표시자를 제거해야 한다."""

    prompt = "저는 신동엽 원장입니다, 병원 홈페이지 공지사항 초안 써줘"

    def _fake_ollama_chat(model, messages, options=None):
        system_content = messages[0]["content"]
        if "목적을 한 문장으로 요약" in system_content:
            return _fake_chat('{"purpose": "[ORGANIZATION] 홈페이지 공지사항 초안 작성"}')
        if "필요한 정보인지 판단" in system_content:
            return _fake_chat('{"신동엽 원장": false, "병원": true}')
        return _fake_chat("[ORGANIZATION] 홈페이지 공지사항 초안 작성해줘")

    with patch("app.rewrite.purpose_flow.detect_llm") as mock_detect_llm, \
         patch("ollama.chat", side_effect=_fake_ollama_chat):

        mock_detect_llm.return_value = {
            "PERSON": [{"text": "신동엽 원장"}],
            "ADDRESS": [],
            "ORGANIZATION": [{"text": "병원"}],
        }

        result = rewrite_with_purpose(prompt)

    assert "[ORGANIZATION]" not in result.purpose
    assert "[ORGANIZATION]" not in result.rewritten
