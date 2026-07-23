import re


BUSINESS_NUMBER_PATTERN = re.compile(
    r"(?<!\d)"
    r"\d{3}-\d{2}-\d{5}"
    r"(?!\d)"
)


def validate_business_number(number):
    """
    사업자등록번호 검증
    123-45-67890 형식
    """

    digits = number.replace("-", "")

    if len(digits) != 10:
        return False


    weights = [
        1, 3, 7, 1, 3,
        7, 1, 3, 5
    ]


    total = 0


    for i in range(9):

        total += int(digits[i]) * weights[i]


    total += (int(digits[8]) * 5) // 10


    check_digit = (10 - (total % 10)) % 10


    return check_digit == int(digits[-1])



def detect_business_number(text):

    results = []


    for match in BUSINESS_NUMBER_PATTERN.finditer(text):

        value = match.group()


        if validate_business_number(value):

            results.append(
                {
                    "type": "BUSINESS_NUMBER",
                    "value": value,
                    "start": match.start(),
                    "end": match.end()
                }
            )


    return results