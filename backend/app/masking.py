#마스커 구현

def mask_prompt(text, entities):

    masked_prompt = text

    # 긴 문자열부터 변경해야 위치 오류 방지
    entities = sorted(
        entities,
        key=lambda x: len(x["value"]),
        reverse=True
    )

    for entity in entities:

        value = entity["value"]
        category = entity["type"]

        masked_prompt = masked_prompt.replace(
            value,
            f"[{category}]"
        )

    return masked_prompt