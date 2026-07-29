"""
app/rewrite/llm_polish.py 테스트.

exaone3.5:2.4b가 user_prompt의 "출력:" 라벨을 그대로 따라 쓰는 경우가 있어서,
polish_with_llm()이 응답에서 그 라벨을 잘라내는지 확인한다. ollama 호출은
mock 처리해서 로컬 모델 없이도 CI에서 돌아간다.
"""

from unittest.mock import patch

from app.rewrite.llm_polish import polish_with_llm


def _fake_chat(content: str):
    return {"message": {"content": content}}


def test_strips_leading_output_label():
    with patch("app.rewrite.llm_polish.ollama.chat") as mock_chat:
        mock_chat.return_value = _fake_chat("출력: 담당자한테 문의 이메일 작성해줘")
        result = polish_with_llm("담당자한테 문의 이메일 좀 써줘")

    assert result == "담당자한테 문의 이메일 작성해줘"


def test_strips_output_label_with_full_width_colon():
    with patch("app.rewrite.llm_polish.ollama.chat") as mock_chat:
        mock_chat.return_value = _fake_chat("출력：담당자한테 문의 이메일 작성해줘")
        result = polish_with_llm("담당자한테 문의 이메일 좀 써줘")

    assert result == "담당자한테 문의 이메일 작성해줘"


def test_leaves_normal_output_untouched():
    with patch("app.rewrite.llm_polish.ollama.chat") as mock_chat:
        mock_chat.return_value = _fake_chat("담당자한테 문의 이메일 작성해줘")
        result = polish_with_llm("담당자한테 문의 이메일 좀 써줘")

    assert result == "담당자한테 문의 이메일 작성해줘"
