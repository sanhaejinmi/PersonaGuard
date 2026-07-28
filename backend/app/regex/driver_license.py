import re


def detect_driver_license(prompt):

    driver_pattern = r"(?<!\d)\d{2}-\d{2}-\d{6}-\d{2}(?!\d)"

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