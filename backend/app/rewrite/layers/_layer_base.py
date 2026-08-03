"""타입별 재작성 레이어(person/organization/address)가 공유하는 LLM 호출 헬퍼.

각 레이어는 "목적 + 이 타입의 엔티티 목록(값·필요성) + 현재까지 다듬어진 문장"을
입력으로 받아, 그 타입에 관련된 언급만 정리한 문장을 돌려준다. 여러 레이어가
순서대로 체이닝되면서(§ purpose_flow.py) 문장을 점점 다듬어 나간다 — 예전처럼
기계적으로 지운 뒤 마지막에 LLM 한 번으로 전체를 다듬는 대신, 타입별로 좁은
범위만 판단하게 해서 더 정확한 재작성을 노린다(사용자 설계 의도, 2026-07-29).
"""

import json
import re

import ollama

MODEL_NAME = "exaone3.5:2.4b"


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:\w+)?", "", text)
    text = re.sub(r"```$", "", text)
    return text.strip()


def run_layer_llm(system_prompt: str, purpose: str, entities: list, text: str) -> str:
    """레이어 공통 LLM 호출. 실패하거나 빈 응답이면 원문(text)을 그대로 반환한다
    (안전한 폴백 — 레이어 하나가 실패해도 전체 파이프라인이 죽지 않는다)."""

    if not entities:
        return text

    user_prompt = (
        f"목적: {purpose}\n"
        f"항목: {json.dumps(entities, ensure_ascii=False)}\n"
        f"문장: {text}"
    )

    try:
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": 0.1, "top_p": 0.2},
        )
        rewritten = _strip_markdown_fence(response["message"]["content"])
    except Exception:
        return text

    return rewritten if rewritten else text
