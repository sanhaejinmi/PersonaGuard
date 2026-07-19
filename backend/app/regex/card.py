import re


def detect_card(prompt):
    """
    신용카드 번호 탐지
    """

    card_pattern = r"(?:\d{4}[- ]?){3}\d{4}"

    result = []

    for match in re.finditer(card_pattern, prompt):

        card = match.group()

        result.append(
            {
                "type": "CARD",
                "value": card,
                "start": match.start(),
                "end": match.end(),
            }
        )

    return result