"""app/rewrite/layers/* 테스트. ollama 호출은 전부 patch한다."""

from unittest.mock import patch

from app.rewrite.layers.address_layer import rewrite_address_layer
from app.rewrite.layers.contact_and_id_layer import rewrite_contact_and_id_layer
from app.rewrite.layers.organization_layer import rewrite_organization_layer
from app.rewrite.layers.person_layer import rewrite_person_layer


def _fake_chat(content: str):
    return {"message": {"content": content}}


def test_contact_and_id_layer_replaces_known_type_with_specific_label():
    text = rewrite_contact_and_id_layer(
        "제 번호는 010-1234-5678입니다", [{"type": "PHONE", "value": "010-1234-5678"}]
    )
    assert "010-1234-5678" not in text
    assert "(연락처 비식별화)" in text


def test_contact_and_id_layer_falls_back_to_generic_label_for_unmapped_type():
    text = rewrite_contact_and_id_layer(
        "학번은 20231234입니다", [{"type": "STUDENT_ID", "value": "20231234"}]
    )
    assert "20231234" not in text
    assert "(개인정보 비식별화)" in text


def test_contact_and_id_layer_skips_missing_values():
    text = rewrite_contact_and_id_layer("아무 문장", [{"type": "PHONE", "value": "010-0000-0000"}])
    assert text == "아무 문장"


def test_person_layer_returns_text_unchanged_when_no_entities():
    with patch("app.rewrite.layers._layer_base.ollama.chat") as mock_chat:
        result = rewrite_person_layer("문장 그대로", "아무 목적", [])
    mock_chat.assert_not_called()
    assert result == "문장 그대로"


def test_person_layer_calls_llm_with_purpose_and_entities():
    with patch("app.rewrite.layers._layer_base.ollama.chat") as mock_chat:
        mock_chat.return_value = _fake_chat("정리된 문장")
        result = rewrite_person_layer(
            "김철수입니다, 인사팀에 문의 메일 좀 써줘",
            "인사팀 문의 메일 작성",
            [{"value": "김철수", "necessary": False}],
        )

    assert result == "정리된 문장"
    sent_user_prompt = mock_chat.call_args.kwargs["messages"][1]["content"]
    assert "인사팀 문의 메일 작성" in sent_user_prompt
    assert "김철수" in sent_user_prompt


def test_organization_layer_falls_back_to_original_text_on_llm_failure():
    with patch(
        "app.rewrite.layers._layer_base.ollama.chat", side_effect=RuntimeError("no model")
    ):
        result = rewrite_organization_layer(
            "삼성전자 다니는데 문의 메일 좀 써줘",
            "문의 메일 작성",
            [{"value": "삼성전자", "necessary": True}],
        )

    assert result == "삼성전자 다니는데 문의 메일 좀 써줘"


def test_address_layer_falls_back_to_original_text_on_empty_llm_response():
    with patch("app.rewrite.layers._layer_base.ollama.chat") as mock_chat:
        mock_chat.return_value = _fake_chat("")
        result = rewrite_address_layer(
            "강남구에 사는데 맛집 추천해줘",
            "맛집 추천",
            [{"value": "강남구", "necessary": True}],
        )

    assert result == "강남구에 사는데 맛집 추천해줘"
