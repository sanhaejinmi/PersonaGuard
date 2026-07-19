from app.eeve_client import detect_llm

prompt = """
    이름은 홍길동입니다.
    전화번호는 010-1234-5678이고
    이메일은 hong@test.com 입니다.
    주민번호는 900101-1234567 입니다.
    안녕하세요.
    제 이름은 김철수입니다.
    성신여자대학교 학생입니다.
    서울시 강남구에 살고 있습니다.
    """

result = detect_llm(prompt)

print(result)