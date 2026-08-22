import re


def detect_email(prompt):
    """
    이메일 탐지
    """

    email_pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"

    result = []

    for match in re.finditer(email_pattern, prompt):
        result.append(
            {
                "type": "EMAIL",
                "value": match.group(),
                "start": match.start(),
                "end": match.end(),
            }
        )

    return result