import re


def validate_business_number(number):
    """
    사업자등록번호 유효성 검증

    True : 정상
    False : 잘못된 번호
    """

    number = number.replace("-", "")

    if len(number) != 10:
        return False

    if not number.isdigit():
        return False

    nums = list(map(int, number))

    weights = [1, 3, 7, 1, 3, 7, 1, 3, 5]

    total = 0

    for i in range(9):
        total += nums[i] * weights[i]

    total += (nums[8] * 5) // 10

    check = (10 - (total % 10)) % 10

    return check == nums[9]



def detect_business_number(prompt):
    """
    사업자등록번호 탐지
    """

    business_pattern = r"\d{3}-?\d{2}-?\d{5}"

    result = []


    for match in re.finditer(business_pattern, prompt):

        number = match.group()


        # MVP 단계에서는 탐지만 수행
        result.append(
            {
                "type": "BUSINESS_NUMBER",
                "value": number,
                "start": match.start(),
                "end": match.end(),
            }
        )


    return result