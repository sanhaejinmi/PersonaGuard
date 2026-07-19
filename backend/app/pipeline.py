from app.regex_engine import detect_regex
from app.actions.masking import mask_prompt
from app.eeve_client import detect_llm
from app.actions.replace_client import replace_personal_info


def process_user_input(text):

    # 1. Regex 탐지
    regex_entities = detect_regex(text)
    print("Regex 탐지 완료")

    # 2. Regex 처리
    if regex_entities:
        regex_masked = mask_prompt(text, regex_entities)
    else:
        regex_masked = text

    print("Regex 처리 완료")

    # 3. LLM 탐지
    llm_entities = detect_llm(regex_masked)
    print("LLM 탐지 완료")

    # 4. LLM 치환
    replaced = replace_personal_info(
        regex_masked,
        llm_entities
    )

    print("LLM 치환 완료")

    return {
        "original": text,
        "regex_entities": regex_entities,
        "regex_masked": regex_masked,
        "llm_entities": llm_entities,
        "replaced": replaced
    }