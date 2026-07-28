import re

from app.actions.policy import POLICY
from app.actions.masking import mask_value

from app.replace.replace_email import replace_email
from app.replace.replace_address import replace_address
from app.replace.replace_organization import replace_organization

from app.rewrite_masked_prompt import rewrite_masked_prompt


_PERSON_BLACKLIST = {
    "교수", "학생", "선생님", "선생", "대표", "회장", "사장",
    "이사", "원장", "감독", "팀장", "대리", "과장", "부장",
    "사원", "직원", "고객", "환자", "저자", "작가", "기자",
    "박사", "교사", "강사", "조교", "연구원", "매니저",
    "부모님", "아버지", "어머니", "선배", "후배", "친구",
}

_ORGANIZATION_BLACKLIST = {
    "인턴", "알바", "아르바이트", "직원", "사원", "대리",
    "과장", "부장", "팀장", "이사", "대표", "회장", "사장",
    "교수", "강사", "조교", "연구원", "매니저", "고객",
    "학생", "수강생", "청강생", "졸업생", "재학생",
    "봉사자", "자원봉사", "파트타이머", "프리랜서",
}


def mask_person(name):
    if len(name) <= 1:
        return "*"
    return name[0] + "*" * (len(name) - 1)


def _is_valid_person_name(value):
    if not value:
        return False
    value = value.strip()
    if re.search(r"[0-9\-]", value):
        return False
    if value in _PERSON_BLACKLIST:
        return False
    if value.endswith(tuple(_PERSON_BLACKLIST)):
        stripped = value
        for title in _PERSON_BLACKLIST:
            if value.endswith(title) and value != title:
                stripped = value[:-len(title)].strip()
                break
        if stripped == "" or stripped in _PERSON_BLACKLIST:
            return False
    return bool(re.fullmatch(r"[가-힣A-Za-z\s]{2,10}", value))


def _is_valid_organization(value):
    if not value:
        return False
    value = value.strip()
    if value in _ORGANIZATION_BLACKLIST:
        return False
    if len(value) <= 2 and not any(
        k in value for k in ("원", "청", "처", "부")
    ):
        return False
    return True


def _is_overlapping(a, b):
    return a["start"] < b["end"] and a["end"] > b["start"]


def apply_policy(original_text, regex_entities, llm_entities):

    entities = []
    mask_info = []

    for entity in regex_entities:
        entities.append({
            "type": entity["type"],
            "value": entity["value"],
            "start": entity["start"],
            "end": entity["end"]
        })

    for entity_type, values in llm_entities.items():
        for item in values:
            text = item["text"]
            if entity_type == "PERSON" and not _is_valid_person_name(text):
                continue
            if entity_type == "ORGANIZATION" and not _is_valid_organization(text):
                continue
            entities.append({
                "type": entity_type,
                "value": text,
                "start": item["start"],
                "end": item["end"]
            })

    entities.sort(key=lambda x: (x["start"], -(x["end"] - x["start"])))

    filtered = []
    for entity in entities:
        overlap = False
        for saved in filtered:
            if _is_overlapping(entity, saved):
                overlap = True
                break
        if not overlap:
            filtered.append(entity)

    result = original_text
    filtered.sort(key=lambda x: x["start"], reverse=True)

    for entity in filtered:
        entity_type = entity["type"]
        value = entity["value"]
        action = POLICY.get(entity_type, "mask")

        if action == "mask":
            if entity_type == "PERSON":
                new_value = mask_person(value)
            else:
                new_value = mask_value(value, entity_type)

        elif action == "replace":
            if entity_type == "EMAIL":
                new_value = replace_email(value)
            elif entity_type == "ADDRESS":
                new_value = replace_address(value)
            elif entity_type == "ORGANIZATION":
                new_value = replace_organization(value)
            else:
                new_value = value

        else:
            new_value = value

        mask_info.append({
            "type": entity_type,
            "original": value,
            "masked": new_value
        })

        result = result[:entity["start"]] + new_value + result[entity["end"]:]

    mask_info.reverse()
    masked_text = result
    rewritten_text = rewrite_masked_prompt(masked_text, mask_info)

    return {
        "masked_text": masked_text,
        "rewritten_text": rewritten_text
    }