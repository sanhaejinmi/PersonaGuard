import random
#당장 필요는 없음

def luhn_check(number):
    """
    카드번호 Luhn 검증
    """

    digits = list(map(int, number))

    checksum = 0

    # 오른쪽부터 두 번째 숫자부터 변환
    reverse_digits = digits[::-1]


    for i, digit in enumerate(reverse_digits):

        if i % 2 == 1:

            digit *= 2

            if digit > 9:
                digit -= 9


        checksum += digit


    return checksum % 10 == 0



def generate_card_number():
    """
    Luhn 검증 통과 16자리 카드번호 생성
    """

    while True:

        # 첫 자리 카드사 prefix
        prefix = random.choice([
            "4",   # VISA
            "5",   # MASTER
            "9"
        ])


        body = "".join(
            str(random.randint(0, 9))
            for _ in range(14)
        )


        number_without_check = prefix + body


        # 마지막 자리 계산
        for check_digit in range(10):

            candidate = (
                number_without_check
                + str(check_digit)
            )


            if luhn_check(candidate):

                return candidate



def replace_card():
    """
    카드번호 재생성

    출력 형식:
    XXXX-XXXX-XXXX-XXXX
    """

    card_number = generate_card_number()


    return (
        card_number[:4]
        + "-"
        + card_number[4:8]
        + "-"
        + card_number[8:12]
        + "-"
        + card_number[12:]
    )