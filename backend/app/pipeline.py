from app.regex_engine import detect_regex
from app.masking import mask_prompt

from app.eeve_client import detect_llm
from app.llm_masking_1 import mask_text
from app.replace_client import replace_personal_info


def process_user_input(text):

    # --------------------
    # 1.Regex 탐지
    # --------------------

    regex_entities = detect_regex(text)

    print("Regex 탐지 완료")

    # --------------------
    # 2.Regex 마스킹
    # --------------------

    if regex_entities:

        regex_masked = mask_prompt(
            text,
            regex_entities
        )

    else:

        regex_masked = text

    print("Regex 마스킹 완료")

    # --------------------
    # 3.LLM 탐지
    # --------------------

    llm_entities = detect_llm(regex_masked)

    print("LLM 탐지 완료")

    # --------------------
    # 4.LLM 마스킹
    # --------------------

    final_masked = mask_text(
        regex_masked,
        llm_entities
    )

    replaced = replace_personal_info(text)

    return {

        "original": text,

        "regex_entities": regex_entities,

        "regex_masked": regex_masked,

        "llm_entities": llm_entities,

        "final_masked": final_masked,

        "replaced": replaced
    }