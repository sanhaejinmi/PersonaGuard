import re


def detect_foreigner_registration(prompt):
    """
    외국인등록번호 탐지
    900101-5123456 (뒷자리 첫 숫자 5~8)
    """

    pattern = r"(?<!\d)\d{6}-[5-8]\d{6}(?!\d)"

    result = []

    for match in re.finditer(pattern, prompt):
        result.append(
            {
                "type": "FOREIGNER_REGISTRATION",
                "value": match.group(),
                "start": match.start(),
                "end": match.end(),
            }
        )

    return result