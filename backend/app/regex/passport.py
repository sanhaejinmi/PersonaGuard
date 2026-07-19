import re


def detect_passport(prompt):
    """
    여권번호 탐지
    """

    passport_pattern = r"\b[A-Z][0-9]{8}\b"

    result = []

    for match in re.finditer(passport_pattern, prompt):
        result.append(
            {
                "type": "PASSPORT",
                "value": match.group(),
                "start": match.start(),
                "end": match.end(),
            }
        )

    return result