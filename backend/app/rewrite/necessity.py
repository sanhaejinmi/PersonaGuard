"""STEP2+3 — 목적(purpose)을 기준으로 각 엔티티가 필요한 정보인지 판단한다.

독립 모듈이다 — pipeline.py/main.py에는 연결되어 있지 않다 (purpose_flow.py 참고).
"""

import json
import re

import ollama

_SYSTEM_PROMPT = """
당신은 문장의 목적과 그 안에 등장하는 개인정보 항목들을 보고, 각 항목이
그 목적을 달성하는 데 꼭 필요한 정보인지 판단하는 AI입니다.

[규칙]
- 각 항목에 대해 true(필요) 또는 false(불필요)만 판단한다.
- 이름, 학번, 전화번호 같은 식별 정보는 대부분 목적 달성에 불필요하다.
- 신분(학생/직원 등)이나 소속 자체가 요청의 맥락으로 꼭 필요한 경우에만 true.
- JSON만 출력한다: {"항목값": true 또는 false, ...}
- 설명하지 않는다.
- Markdown을 사용하지 않는다.

[예시]
목적: 교수님께 결석 사실을 알리는 이메일 작성
항목: ["김철수", "성신여자대학교", "010-1234-5678"]
출력: {"김철수": false, "성신여자대학교": true, "010-1234-5678": false}
"""


def _strip_fence(content: str) -> str:
    content = content.strip()
    content = re.sub(r"^```(?:json)?", "", content)
    content = re.sub(r"```$", "", content)
    return content.strip()


def classify_necessity(purpose: str, entities: list) -> dict:
    """entities: [{"type": ..., "value": ...}, ...]

    반환: {value: True(필요)/False(불필요)}. 호출 실패·파싱 실패 시 보수적으로
    전부 False(불필요 → 비식별화 쪽)로 처리한다.

    exaone3.5:7.8b 사용 — CLAUDE.md §8이 확정한 exaone3.5:2.4b와 다르다.
    purpose_flow.py 전용 실험적 오버라이드다 (purpose.py 참고).
    """

    if not entities:
        return {}

    values = sorted({e["value"] for e in entities})

    try:
        response = ollama.chat(
            model="exaone3.5:7.8b",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"목적: {purpose}\n항목: {json.dumps(values, ensure_ascii=False)}",
                },
            ],
            options={"temperature": 0.1, "top_p": 0.2},
        )
        content = _strip_fence(response["message"]["content"])
    except Exception:
        return {value: False for value in values}

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {value: False for value in values}

    if not isinstance(data, dict):
        return {value: False for value in values}

    return {value: bool(data.get(value, False)) for value in values}
