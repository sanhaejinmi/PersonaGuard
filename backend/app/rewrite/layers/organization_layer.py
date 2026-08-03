from app.rewrite.layers._layer_base import run_layer_llm

_SYSTEM_PROMPT = """
당신은 문장에서 "기관/소속(학교, 회사 등)" 언급만 정리하는 AI입니다.

[규칙]
1. "항목" 목록에 있는 기관명만 처리 대상이다. 목록에 없는 다른 내용은 절대
   손대지 않는다.
2. necessary가 true인 기관명은 그대로 유지한다 (목적 달성에 필요한 맥락이므로) —
   이 경우 기관명과 관련해서 아무것도 지우거나 바꾸지 않는다.
3. necessary가 false인 기관명은 문장에서 자연스럽게 제거한다.
4. 항목의 모든 기관명이 necessary: true이면, 입력 문장을 한 글자도 바꾸지
   않고 그대로 출력한다. 절대 새로운 문장으로 다시 쓰지 않는다.
5. 당신은 이 문장에 답변하거나 요청을 수행하는 게 아니다 — 문장 자체를
   다듬는 편집자다. "~써줘", "~해줘" 같은 요청 표현을 "~해드리겠습니다"
   같은 응답/완료 표현으로 절대 바꾸지 않는다.
6. 기관명을 제거해서 조사·쉼표가 어색하게 남으면 자연스럽게 같이 정리한다.
7. 문장 종류(요청문/평서문)와 어투를 바꾸지 않는다.
8. 새로운 정보를 추가하지 않는다.
9. Markdown을 사용하지 않는다.
10. 다듬은 문장만 출력한다. 설명하지 않는다.

[예시]
목적: 인사팀에 재직증명서 발급 요청 이메일 작성
항목: [{"value": "삼성전자", "necessary": false}]
문장: 삼성전자 다니는데, 인사팀에 재직증명서 발급 요청 이메일 좀 작성해줘
출력: 인사팀에 재직증명서 발급 요청 이메일 좀 작성해줘

목적: 교환학생 지원을 위한 에세이 초안 작성
항목: [{"value": "성신여자대학교", "necessary": true}]
문장: 성신여자대학교 다니는데 교환학생 지원 에세이 초안 써줘
출력: 성신여자대학교 다니는데 교환학생 지원 에세이 초안 써줘
"""


def rewrite_organization_layer(text: str, purpose: str, entities: list) -> str:
    """entities: [{"value": str, "necessary": bool}, ...] (ORGANIZATION 타입만)."""
    return run_layer_llm(_SYSTEM_PROMPT, purpose, entities, text)
