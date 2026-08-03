"""
app/rewrite/entity_filter.py 테스트.

50개 프롬프트 실험에서 실제로 발견된 exaone의 PERSON/ORGANIZATION 오탐지
케이스(숫자열을 이름으로, 문장 전체를 이름으로, "-님" 경어체 직함을 이름으로)를
회귀 테스트로 고정한다.
"""

from app.rewrite.entity_filter import is_valid_organization, is_valid_person_name


def test_real_name_is_valid():
    assert is_valid_person_name("김철수") is True


def test_numeric_value_is_rejected():
    # 50개 실험 #6 — 학번(20231234)이 PERSON으로 오탐지된 사례
    assert is_valid_person_name("20231234") is False


def test_overlong_phrase_is_rejected():
    # 50개 실험 #13 — "서울대학교 컴퓨터공학과 학생" 전체가 PERSON으로 오탐지된 사례
    assert is_valid_person_name("서울대학교 컴퓨터공학과 학생") is False


def test_bare_title_is_rejected():
    assert is_valid_person_name("교수") is False
    assert is_valid_person_name("팀장") is False


def test_honorific_suffixed_title_is_rejected():
    # 50개 실험에서 발견 — 블랙리스트가 "교수"만 갖고 있어 "교수님"은 못 걸렀었다.
    assert is_valid_person_name("교수님") is False
    assert is_valid_person_name("팀장님") is False
    assert is_valid_person_name("주무관") is False


def test_name_with_role_suffix_keeps_the_name_part_valid():
    # "박지훈 대리"처럼 이름+직함 조합은 여전히 유효한 값으로 취급한다
    # (일반화 대상으로 넘겨서 이름 언급을 제거하는 게 목적).
    assert is_valid_person_name("박지훈 대리") is True


def test_valid_organization_is_accepted():
    assert is_valid_organization("성신여자대학교") is True


def test_role_word_is_rejected_as_organization():
    assert is_valid_organization("인턴") is False
    assert is_valid_organization("학생") is False


def test_title_miscategorized_as_organization_is_rejected():
    # exaone3.5:7.8b 비교 테스트에서 발견 — 2.4b는 직함을 PERSON으로 잘못
    # 넣었는데, 7.8b는 같은 직함을 ORGANIZATION으로 잘못 넣는 경우가 있었다
    # ("주무관"이 PERSON_BLACKLIST에만 있고 ORGANIZATION_BLACKLIST엔 없어서
    # 이 케이스만 안 걸러졌었다).
    assert is_valid_organization("주무관") is False
    assert is_valid_organization("과장") is False


def test_honorific_suffixed_title_is_rejected_as_organization():
    assert is_valid_organization("원장님") is False
