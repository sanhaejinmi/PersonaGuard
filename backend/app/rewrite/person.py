import re

# 별표 있는 이름: 이**, 최유**, 홍길동**
# 뒤에 남는 쉼표/공백까지 함께 지운다 — 안 지우면 "한지민이고, 외국인등록..."에서
# 이름만 빠지고 ", 외국인등록..."처럼 문장 중간에 쉼표가 덩그러니 남아 LLM
# 다듬기 단계가 오히려 문장을 이상하게 뭉개버리는 사례가 있었다(50개 실험 #24).
_NAME_MASKED_PATTERN = re.compile(
    r"[가-힣]+\*+"
    r"(이고|이며|이라|이랑|이나|이은|이는|인데|이가|이를"
    r"|이에|이로|이야|이에요|입니다|이었|이던)?"
    r"[,\s]*"
)

# 이름 제거 후 남는 도입부 잔재
_INTRO_PATTERN = re.compile(
    r"(나는|저는|저|나)\s*(,|이고|이며|이랑|인데)?\s*"
)

_PARTICLE_SUFFIX = (
    r"(이고|이며|이라|이랑|이나|이은|이는|인데"
    r"|이가|이를|이에|이로|이야|이에요|입니다|이었|이던)?"
    r"[,\s]*"
)


def strip_person_mentions(text: str, mask_info: list) -> str:
    """
    PERSON 관련 언급을 문장에서 제거한다.
    - 마스킹되지 않은 원본 이름이 남아있으면 mask_info의 original 값으로 찾아 제거
    - 이미 부분 마스킹된 이름(이**, 최유** 등)은 패턴으로 찾아 제거
    - 이름 제거 후 남는 "저는," 같은 도입부 잔재도 정리
    """

    for item in mask_info:

        if item.get("type") == "PERSON":

            original = item.get("original", "")

            if original and original in text:

                text = re.sub(
                    re.escape(original) + _PARTICLE_SUFFIX,
                    "",
                    text
                )

    text = _NAME_MASKED_PATTERN.sub("", text)
    text = _INTRO_PATTERN.sub("", text)

    return text
