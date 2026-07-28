from app.actions.policy import POLICY
import ollama


def replace_personal_info(text, entities):
    """
    LLM 탐지 결과 기반 개인정보 치환

    entities 형태:

    {
        "PERSON": ["이수민"],
        "ORGANIZATION": ["금천고등학교"]
    }

    """

    if not entities:
        return text


    replacements = {}


    # =================================
    # 개인정보별 치환값 생성
    # =================================

    for category, items in entities.items():

        if POLICY.get(category) != "replace":
            continue


        for item in items:


            # 이름
            if category == "PERSON":

                replacements[item] = "[사용자 이름]"



            # 주소
            elif category == "ADDRESS":

                replacements[item] = "[주소]"



            # 학교/기관
            elif category == "ORGANIZATION":

                replacements[item] = "[기관명]"



            # 기타
            else:

                replacements[item] = "[개인정보]"



    # =================================
    # 실제 문자열 치환
    # =================================

    for original, replaced in replacements.items():

        text = text.replace(
            original,
            replaced
        )


    return text