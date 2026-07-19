import random


def replace_phone(value: str) -> str:
    """
    전화번호 치환

    예:
    010-1234-5678

    ->
    010-XXXX-XXXX
    """

    if "-" in value:

        parts = value.split("-")

        return (
            f"{parts[0]}-"
            f"{random.randint(1000,9999)}-"
            f"{random.randint(1000,9999)}"
        )


    return "010-0000-0000"