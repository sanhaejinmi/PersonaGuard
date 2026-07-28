"""STEP1 — 프롬프트 전체의 목적을 한 문장으로 추론한다.

독립 모듈이다 — pipeline.py/main.py에는 연결되어 있지 않다 (설계는 승인됐으나
실제 연동은 보류 요청에 따라 하지 않음, purpose_flow.py 참고).
"""

import json
import re

import ollama

_SYSTEM_PROMPT = """
당신은 사용자 프롬프트의 목적을 한 문장으로 요약하는 AI입니다.

[규칙]
- 사용자가 최종적으로 원하는 행동/결과가 무엇인지 한 문장으로 요약한다.
- 개인정보(이름, 연락처, 소속 등)는 요약에 포함하지 않는다.
- 입력 문장에 [PHONE], [EMAIL], [RRN] 같은 대괄호 표시가 있어도, 그 표시를
  요약 문장에 그대로 옮기지 않는다 (해당 정보가 있었다는 사실 자체를 요약에
  담지 않는다).
- JSON만 출력한다: {"purpose": "..."}
- 설명하지 않는다.
- Markdown을 사용하지 않는다.

[예시]
입력: 김철수입니다, 성신여자대학교 학생인데 010-1234-5678로 연락 가능합니다. 교수님한테 결석계 이메일 좀 써줘
출력: {"purpose": "교수님께 결석 사실을 알리는 이메일 작성"}
"""


def _strip_fence(content: str) -> str:
    content = content.strip()
    content = re.sub(r"^```(?:json)?", "", content)
    content = re.sub(r"```$", "", content)
    return content.strip()


def infer_purpose(prompt: str) -> str:
    """실패하거나 파싱할 수 없으면 빈 문자열을 반환한다.

    exaone3.5:7.8b 사용 — CLAUDE.md §8이 확정한 exaone3.5:2.4b와 다르다.
    purpose_flow.py 전용 실험적 오버라이드이며, 실제 서비스 확정 모델을
    바꾸는 게 아니다 (2.4b가 여러 프롬프트에서 요청문을 완성된 응답/문서로
    바꿔버리는 문제가 재현돼서, 이 실험 흐름에서만 7.8b로 테스트해보는 것).
    """

    try:
        response = ollama.chat(
            model="exaone3.5:7.8b",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0.1, "top_p": 0.2},
        )
        content = _strip_fence(response["message"]["content"])
    except Exception:
        return ""

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return ""

    return str(data.get("purpose", "")) if isinstance(data, dict) else ""
