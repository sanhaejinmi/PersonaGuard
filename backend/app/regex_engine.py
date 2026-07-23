from app.regex.phone import detect_phone
from app.regex.email import detect_email
from app.regex.rrn import detect_rrn
from app.regex.bank_account import detect_bank_account
from app.regex.card import detect_card
from app.regex.business_number import detect_business_number
from app.regex.passport import detect_passport
from app.regex.driver_license import detect_driver_license



def detect_regex(prompt):
    """
    Regex 기반 개인정보 전체 탐지
    """

    result = []

    result.extend(detect_phone(prompt))
    result.extend(detect_email(prompt))
    result.extend(detect_rrn(prompt))
    result.extend(detect_bank_account(prompt))
    result.extend(detect_card(prompt))
    result.extend(detect_business_number(prompt))
    result.extend(detect_passport(prompt))
    result.extend(detect_driver_license(prompt))


    # =====================================
    # 중복 Entity 제거
    # RRN 우선 처리
    # =====================================

    filtered_result = []


    # 긴 범위 우선 정렬
    result.sort(
        key=lambda x: (
            x["start"],
            -(x["end"] - x["start"])
        )
    )


    for entity in result:

        overlap = False


        for saved in filtered_result:


            # entity가 saved 내부에 포함되는 경우
            if (
                entity["start"] >= saved["start"]
                and entity["end"] <= saved["end"]
            ):


                # 주민번호 내부의 사업자번호 제거
                if (
                    saved["type"] == "RRN"
                    and entity["type"] == "BUSINESS_NUMBER"
                ):
                    overlap = True
                    break


                # 일반적인 중복 제거
                overlap = True
                break



        if not overlap:
            filtered_result.append(entity)



    # 최종 위치 정렬

    filtered_result.sort(
        key=lambda x: x["start"]
    )


    return filtered_result