import re


def detect_passport(prompt):

    passport_pattern = r"(?<![A-Za-z0-9])[A-Z][0-9]{8}(?![A-Za-z0-9])"

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