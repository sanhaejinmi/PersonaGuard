import re


def validate_rrn(rrn):
    """
    주민등록번호 유효성 검증
    """

    rrn = rrn.replace("-", "")

    if len(rrn) != 13:
        return False

    if not rrn.isdigit():
        return False

    numbers = list(map(int, rrn))

    weights = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]

    total = 0

    for i in range(12):
        total += numbers[i] * weights[i]

    check = (11 - (total % 11)) % 10

    return check == numbers[12]



def detect_rrn(prompt):
    """
    주민등록번호 탐지
    """

    rrn_pattern = r"\d{6}-?[1-4]\d{6}"

    result = []


    for match in re.finditer(rrn_pattern, prompt):

        rrn = match.group()


        # MVP 단계에서는 탐지만 수행
        result.append(
            {
                "type": "RRN",
                "value": rrn,
                "start": match.start(),
                "end": match.end(),
            }
        )


    return result