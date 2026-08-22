from app.regex.phone import detect_phone
from app.regex.email import detect_email
from app.regex.rrn import detect_rrn
from app.regex.bank_account import detect_bank_account
from app.regex.card import detect_card
from app.regex.business_number import detect_business_number
from app.regex.passport import detect_passport
from app.regex.driver_license import detect_driver_license
from app.regex.foreigner_registration import detect_foreigner_registration


def _is_overlapping(a, b):
    return a["start"] < b["end"] and a["end"] > b["start"]


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
    result.extend(detect_foreigner_registration(prompt))

    filtered_result = []

    result.sort(
        key=lambda x: (
            x["start"],
            -(x["end"] - x["start"])
        )
    )

    for entity in result:

        overlap = False

        for saved in filtered_result:

            if _is_overlapping(entity, saved):
                overlap = True
                break

        if not overlap:
            filtered_result.append(entity)

    filtered_result.sort(key=lambda x: x["start"])

    return filtered_result