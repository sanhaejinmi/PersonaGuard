from app.regex_engine import detect_regex



def test_regex_engine():

    prompt = """
    사용자 정보 테스트

    이름: 김철수

    이메일:
    kim.test@gmail.com

    전화번호:
    010-1234-5678

    주민등록번호:
    900101-1234567

    IP 주소:
    192.168.0.10

    카드번호:
    1234-5678-1234-5678

    URL:
    https://example.com
    """


    print("\n===== ORIGINAL TEXT =====")
    print(prompt)



    results = detect_regex(prompt)



    print("\n===== DETECTION RESULT =====")

    for result in results:
        print(result)



if __name__ == "__main__":
    test_regex_engine()