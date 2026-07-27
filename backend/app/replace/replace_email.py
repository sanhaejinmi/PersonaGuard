import random
import string


EMAIL_DOMAINS = [
    "naver.com",
    "gmail.com",
    "daum.net",
    "kakao.com"
]


def replace_email(value: str) -> str:
    """
    이메일을 랜덤 이메일로 치환

    hong@test.com
    ↓
    jalyyyy@naver.com
    """

    username = "".join(
        random.choices(
            string.ascii_lowercase,
            k=7
        )
    )

    domain = random.choice(EMAIL_DOMAINS)

    return f"{username}@{domain}"