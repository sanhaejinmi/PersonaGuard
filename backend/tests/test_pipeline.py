from app.pipeline import process_user_input


text = """
안녕하세요.

제 이름은 홍길동입니다.

전화번호는 010-1234-5678입니다.

메일은 hong@test.com입니다.

주민번호는 900101-1234567입니다.

성신여자대학교 학생입니다.

서울특별시 강남구에 살고 있습니다.
"""


result = process_user_input(text)


print()

print("=" * 60)

print("원본")

print(result["original"])

print()

print("=" * 60)

print("Regex 탐지")

print(result["regex_entities"])

print()

print("=" * 60)

print("Regex 마스킹")

print(result["regex_masked"])

print()

print("=" * 60)

print("LLM 탐지")

print(result["llm_entities"])

print()

print("=" * 60)

print("최종 마스킹")

print(result["final_masked"])

print()

print("="*60)

print("LLM 치환")

print(result["replaced"])