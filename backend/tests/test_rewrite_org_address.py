"""
app/rewrite/org_address_label.py 및 orchestrator 통합 테스트.

pipeline.py._replacement_for()가 ORGANIZATION/ADDRESS를 고정 라벨 '[기관]'/'[주소]'로
치환해 넣는데, rewrite_masked_prompt()가 이 라벨을 그대로 두면 재작성 결과에
'[기관]' 문자열이 노출된다. 이 테스트는 그 라벨이 LLM 다듬기 이전에 이미 제거되고,
최종 결과에도 남지 않는지 확인한다. ollama 호출은 로컬 모델 없이도 CI에서 돌아가도록
patch한다 (test_pipeline.py의 detect_llm patch 관례와 동일).
"""

from unittest.mock import patch

from app.rewrite.label_strip import strip_disclosure_labels
from app.rewrite.orchestrator import rewrite_masked_prompt
from app.rewrite.org_address_label import normalize_org_address_labels


def _fake_chat(content: str):
    return {"message": {"content": content}}


def test_normalize_org_placeholder_to_disclosure_label():
    text = "저는 [기관] 소속인데 문의 이메일 좀 써줘"
    normalized = normalize_org_address_labels(text)
    assert "[기관]" not in normalized
    assert "(기관 비식별화)" in normalized


def test_normalize_address_placeholder_to_disclosure_label():
    text = "저는 [주소]에 살고 있는데 근처 병원 추천해줘"
    normalized = normalize_org_address_labels(text)
    assert "[주소]" not in normalized
    assert "(주소 비식별화)" in normalized


def test_strip_disclosure_labels_removes_org_label_and_preceding_word():
    text = normalize_org_address_labels("저는 [기관] 소속인데 문의 이메일 좀 써줘")
    stripped = strip_disclosure_labels(text)
    assert "기관" not in stripped
    assert "비식별화" not in stripped


def test_org_placeholder_never_reaches_llm_input():
    masked_text = "저는 [기관] 소속인데 담당자한테 문의 이메일 좀 써줘"

    with patch("app.rewrite.llm_polish.ollama.chat") as mock_chat:
        mock_chat.return_value = _fake_chat("담당자한테 문의 이메일 작성해줘")
        rewrite_masked_prompt(masked_text, mask_info=[])
        sent_user_prompt = mock_chat.call_args.kwargs["messages"][1]["content"]

    assert "[기관]" not in sent_user_prompt


def test_org_placeholder_absent_from_final_result():
    masked_text = "저는 [기관] 소속인데 담당자한테 문의 이메일 좀 써줘"

    with patch("app.rewrite.llm_polish.ollama.chat") as mock_chat:
        mock_chat.return_value = _fake_chat("담당자한테 문의 이메일 작성해줘")
        result = rewrite_masked_prompt(masked_text, mask_info=[])

    assert "[기관]" not in result


def test_address_placeholder_absent_from_final_result():
    masked_text = "저는 [주소]에 살고 있는데 근처 병원 추천해줘"

    with patch("app.rewrite.llm_polish.ollama.chat") as mock_chat:
        mock_chat.return_value = _fake_chat("근처 병원 추천해줘")
        result = rewrite_masked_prompt(masked_text, mask_info=[])

    assert "[주소]" not in result
