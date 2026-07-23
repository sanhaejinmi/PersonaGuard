import re

BANK_PATTERNS = {
    "국민은행": r"\d{3,6}-\d{2}-\d{6}",
    "신한은행": r"\d{3}-\d{2}-\d{6}",
    "우리은행": r"\d{3}-\d{4}-\d{6}",
    "하나은행": r"\d{3}-\d{6}-\d{5}",
    "농협은행": r"\d{3}-\d{4}-\d{4}-\d{2}",
    "카카오뱅크": r"\d{4}-\d{2}-\d{7}",
    "토스뱅크": r"\d{3}-\d{4}-\d{4}",
}


def detect_bank_account(prompt):

    result = []

    for bank, pattern in BANK_PATTERNS.items():

        regex = rf"{bank}\s*[:：]?\s*({pattern})"

        for match in re.finditer(regex, prompt):

            result.append(
                {
                    "type": "BANK_ACCOUNT",
                    "value": match.group(1),
                    "start": match.start(1),
                    "end": match.end(1),
                }
            )

    return result