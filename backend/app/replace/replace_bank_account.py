import random



def replace_account(value: str) -> str:
    """
    계좌번호 치환
    """


    formats = [

        # 123-456789-12

        lambda:
        f"{random.randint(100,999)}-"
        f"{random.randint(100000,999999)}-"
        f"{random.randint(10,99)}",


        # 3333-01-1234567

        lambda:
        f"{random.randint(1000,9999)}-"
        f"{random.randint(10,99)}-"
        f"{random.randint(1000000,9999999)}"

    ]


    return random.choice(formats)()