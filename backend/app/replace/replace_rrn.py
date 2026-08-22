import random


def replace_rrn(value: str) -> str:
    """
    주민등록번호 치환
    예:
    090302-4565288
    ->
    900101-1234567 형태의 가상 주민번호
    """

    # 생년월일 유지 (원하면 이것도 랜덤 가능)
    birth = value[:6]

    # 성별코드 유지
    gender = value[7]

    # 뒤 6자리 랜덤 생성
    random_numbers = "".join(
        str(random.randint(0, 9))
        for _ in range(6)
    )

    return f"{birth}-{gender}{random_numbers}"