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
    

    # 위치 기준으로 정렬
    result.sort(key=lambda x: x["start"])

    return result