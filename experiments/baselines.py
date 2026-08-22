"""
실험 1(§6) 비교 대상 탐지기.

app.pipeline.run_analysis()는 읽기 전용으로 호출만 한다 — 이 파일도, 이
패키지의 어떤 파일도 app/ 아래 실서비스 코드를 수정하지 않는다.
"""

from __future__ import annotations

from app.pipeline import run_analysis
from app.regex_engine import detect_regex

# 규칙 방식 2("미리 만든 목록에 있는 단어만 찾는 방법") 비교용 최소 예시 목록.
# 실제 채점 기준이 아니라, "정형화되지 않은 개인정보는 목록에 없으면 놓친다"는
# 단순 규칙 기반 접근의 한계를 보여주기 위한 베이스라인이다.
DEFAULT_NAME_LIST = {"김민준", "이서연", "박지훈", "최유진", "정하늘"}
DEFAULT_ORG_LIST = {"성신여자대학교", "카카오", "서울대학교", "네이버"}


def regex_only_detector(text: str) -> list[dict]:
    """규칙 방식 1 — 정형 개인정보(정규식)만 탐지한다.
    PERSON/ADDRESS/ORGANIZATION은 원리적으로 절대 찾지 못한다."""
    return [
        {"type": e["type"], "value": e["value"], "start": e["start"], "end": e["end"]}
        for e in detect_regex(text)
    ]


def keyword_list_detector(
    text: str,
    name_list: set[str] = DEFAULT_NAME_LIST,
    org_list: set[str] = DEFAULT_ORG_LIST,
) -> list[dict]:
    """규칙 방식 2 — 정규식 탐지 + 미리 정의한 이름/기관 목록에 있는 단어만 추가로 찾는다.
    목록에 없는 이름·기관은 찾지 못한다(이게 이 베이스라인의 핵심 한계)."""
    found = regex_only_detector(text)
    for word_list, entity_type in ((name_list, "PERSON"), (org_list, "ORGANIZATION")):
        for word in word_list:
            start = 0
            while True:
                idx = text.find(word, start)
                if idx == -1:
                    break
                found.append(
                    {"type": entity_type, "value": word, "start": idx, "end": idx + len(word)}
                )
                start = idx + len(word)
    return found


def personaguard_detector(text: str) -> list[dict]:
    """PersonaGuard 실제 탐지 — regex(②) + EEVE 1차 탐색(④), §3 파이프라인 그대로.
    로컬 Ollama 서버 + exaone3.5:2.4b가 필요하다."""
    response = run_analysis(text)
    return [
        {"type": e.type, "value": e.value, "start": e.start, "end": e.end}
        for e in response.entities
    ]
