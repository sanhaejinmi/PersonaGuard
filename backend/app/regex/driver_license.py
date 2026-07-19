import re


def detect_driver_license(prompt):
    """
    운전면허번호 탐지
    """

    driver_pattern = r"\b\d{2}-\d{2}-\d{6}-\d{2}\b"

    result = []

    for match in re.finditer(driver_pattern, prompt):
        result.append(
            {
                "type": "DRIVER_LICENSE",
                "value": match.group(),
                "start": match.start(),
                "end": match.end(),
            }
        )

    return result