from app.regex_engine import detect_regex
from app.eeve_client import detect_llm
from app.actions.apply_policy import apply_policy



def process_text(text):
    """
    개인정보 탐지 + 비식별화 전체 Pipeline

    흐름:
    입력
      ↓
    Regex 탐지
      ↓
    LLM 탐지
      ↓
    Policy 적용
      ↓
    Mask / Replace
      ↓
    결과 반환
    """


    # ==========================
    # 1. Regex 탐지
    # ==========================

    regex_entities = detect_regex(text)



    # ==========================
    # 2. LLM 탐지
    # ==========================

    llm_entities = detect_llm(text)



    # ==========================
    # 3. Policy 적용
    # ==========================

    final_text = apply_policy(
        text,
        regex_entities,
        llm_entities
    )



    # ==========================
    # 결과 반환
    # ==========================

    return {

        "original": text,

        "regex_entities": regex_entities,

        "llm_entities": llm_entities,

        "result": final_text

    }





# =========================================
# CLI 테스트용
# =========================================

if __name__ == "__main__":


    print("=" * 60)

    print("개인정보 비식별화 테스트")

    print("=" * 60)



    print(
        "\n문장을 입력하세요. 입력 종료는 빈 줄입니다.\n"
    )


    lines = []


    while True:


        line = input()


        if line == "":

            break


        lines.append(line)



    text = "\n".join(lines)



    result = process_text(text)



    print("\n" + "=" * 60)

    print("원본")

    print("=" * 60)

    print(
        result["original"]
    )



    print("\n" + "=" * 60)

    print("Regex 탐지 결과")

    print("=" * 60)


    for entity in result["regex_entities"]:

        print(entity)



    print("\n" + "=" * 60)

    print("LLM 탐지 결과")

    print("=" * 60)


    for entity_type, values in result["llm_entities"].items():

        print(f"\n[{entity_type}]")

        for entity in values:

            print(entity)



    print("\n" + "=" * 60)

    print("최종 비식별화 결과")

    print("=" * 60)


    print(
        result["result"]
    )