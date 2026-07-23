import random


def replace_business_number(value: str) -> str:
    """
    사업자등록번호 일부 치환
    예: 123-45-67890 -> 123-45-48271
    """

    front = value[:7]   # 123-45-
    tail = str(random.randint(10000, 99999))

    return front + tail