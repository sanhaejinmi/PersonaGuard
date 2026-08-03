from app.exaone_client import add_position


def test_add_position_handles_normal_dict_items():
    entities = {"PERSON": [{"text": "홍길동"}], "ADDRESS": [], "ORGANIZATION": []}
    result = add_position("홍길동입니다", entities)

    assert result["PERSON"] == [{"text": "홍길동", "start": 0, "end": 3}]
    assert result["ADDRESS"] == []
    assert result["ORGANIZATION"] == []


def test_add_position_handles_plain_string_items():
    # exaone3.5:2.4b가 가끔 {"text": "..."} 대신 문자열을 그대로 반환한다.
    entities = {"PERSON": ["홍길동"], "ADDRESS": [], "ORGANIZATION": []}
    result = add_position("홍길동입니다", entities)

    assert result["PERSON"] == [{"text": "홍길동", "start": 0, "end": 3}]


def test_add_position_skips_items_that_are_neither_dict_nor_str():
    entities = {"PERSON": [123, None, ["nested"]], "ADDRESS": [], "ORGANIZATION": []}
    result = add_position("아무 텍스트", entities)

    assert result["PERSON"] == []


def test_add_position_handles_non_list_entity_value():
    entities = {"PERSON": "홍길동", "ADDRESS": None, "ORGANIZATION": []}
    result = add_position("홍길동입니다", entities)

    assert result["PERSON"] == []
    assert result["ADDRESS"] == []
    assert result["ORGANIZATION"] == []


def test_add_position_handles_non_dict_top_level():
    result = add_position("아무 텍스트", ["not", "a", "dict"])

    assert result == {}


def test_add_position_handles_dict_missing_text_key():
    entities = {"PERSON": [{"name": "홍길동"}], "ADDRESS": [], "ORGANIZATION": []}
    result = add_position("홍길동입니다", entities)

    assert result["PERSON"] == []
