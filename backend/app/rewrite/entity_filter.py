"""LLM(exaone) 탐지 결과 중 실제 이름/기관명이 아닐 가능성이 큰 값을 걸러낸다.

원래 `app/actions/apply_policy.py`에 있던 `_is_valid_person_name`/
`_is_valid_organization`을 그대로 옮기고, 알려진 issue(§2 "제 번호", "주민번호"
같은 일반 명사를 PERSON으로 오탐지) 케이스 중 하나였던 "-님" 경어체 직함
("교수님", "팀장님" 등)을 추가로 걸러내도록 개선했다 — 기존 블랙리스트는
"교수", "팀장"처럼 맨 형태만 들고 있어서 "교수님"은 못 걸렀다.

`apply_policy.py`도 이 모듈을 재사용해서 같은 로직이 두 곳에 중복되지 않는다.
"""

import re

PERSON_BLACKLIST = {
    "교수", "학생", "선생님", "선생", "대표", "회장", "사장",
    "이사", "원장", "감독", "팀장", "대리", "과장", "부장",
    "사원", "직원", "고객", "환자", "저자", "작가", "기자",
    "박사", "교사", "강사", "조교", "연구원", "매니저",
    "부모님", "아버지", "어머니", "선배", "후배", "친구",
    "주무관", "대리인",
}

ORGANIZATION_BLACKLIST = {
    "인턴", "알바", "아르바이트", "직원", "사원", "대리",
    "과장", "부장", "팀장", "이사", "대표", "회장", "사장",
    "교수", "강사", "조교", "연구원", "매니저", "고객",
    "학생", "수강생", "청강생", "졸업생", "재학생",
    "봉사자", "자원봉사", "파트타이머", "프리랜서",
    "주무관", "대리인", "원장", "감독",
}


def is_valid_person_name(value: str) -> bool:
    if not value:
        return False

    value = value.strip()

    if re.search(r"[0-9\-]", value):
        return False

    if value in PERSON_BLACKLIST:
        return False

    # "교수님", "팀장님"처럼 "-님" 경어체가 붙은 직함도 같은 블랙리스트로 걸러낸다.
    normalized = value[:-1] if value.endswith("님") else value
    if normalized in PERSON_BLACKLIST:
        return False

    if value.endswith(tuple(PERSON_BLACKLIST)):
        stripped = value
        for title in PERSON_BLACKLIST:
            if value.endswith(title) and value != title:
                stripped = value[: -len(title)].strip()
                break
        if stripped == "" or stripped in PERSON_BLACKLIST:
            return False

    return bool(re.fullmatch(r"[가-힣A-Za-z\s]{2,10}", value))


def is_valid_organization(value: str) -> bool:
    if not value:
        return False

    value = value.strip()

    if value in ORGANIZATION_BLACKLIST:
        return False

    # "원장님"처럼 "-님" 경어체가 붙은 직함을 exaone이 ORGANIZATION으로 잘못
    # 분류하는 경우도 있어서(§2 오탐지 이슈의 변형), PERSON과 동일하게 정규화해서
    # 블랙리스트로 걸러낸다.
    normalized = value[:-1] if value.endswith("님") else value
    if normalized in ORGANIZATION_BLACKLIST:
        return False

    if len(value) <= 2 and not any(k in value for k in ("원", "청", "처", "부")):
        return False

    return True
