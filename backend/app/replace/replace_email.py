import random
import string



def replace_email(value: str) -> str:
    """
    이메일 치환

    예:
    kim@test.com

    ->
    abcxyz@example.com
    """


    username = "".join(
        random.choice(string.ascii_lowercase)
        for _ in range(6)
    )


    return f"{username}@example.com"