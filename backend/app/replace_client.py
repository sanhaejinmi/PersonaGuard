import ollama


def replace_personal_info(text):

    system_prompt = """
당신은 개인정보 비식별화 AI이다.

입력된 문장의 의미를 유지하면서 개인정보만 자연스러운 가상의 정보로 변경하라.

규칙

- 이름 → 다른 한국 이름
- 주소 → 실제 존재하는 다른 주소
- 학교 → 다른 학교
- 회사 → 다른 회사
- 전화번호 → 형식 유지
- 이메일 → 형식 유지
- 주민등록번호 → 형식만 유지

절대 설명하지 말고

변경된 문장만 출력한다.
"""

    response = ollama.chat(
        model="exaone3.5:2.4b",
        messages=[
            {
                "role":"system",
                "content":system_prompt
            },
            {
                "role":"user",
                "content":text
            }
        ]
    )

    return response["message"]["content"]