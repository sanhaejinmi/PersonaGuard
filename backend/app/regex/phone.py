import re


def detect_phone(prompt):
    """
    전화번호 탐지
    """

    phone_pattern = r"01[016789]-?\d{3,4}-?\d{4}"

    result = []

    for match in re.finditer(phone_pattern, prompt):
        result.append(
            {
                "type": "PHONE",
                "value": match.group(),
                "start": match.start(),
                "end": match.end(),
            }
        )

    return result