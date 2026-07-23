from app.regex_engine import detect_regex
from app.eeve_client import detect_llm
from app.actions.apply_policy import apply_policy



print("=" * 60)
print("개인정보 비식별화 테스트")
print("=" * 60)



# =====================================
# 사용자 입력
# =====================================

print("\n문장을 입력하세요. 입력 종료는 빈 줄입니다.\n")

lines = []

while True:

    line = input()

    if line == "":
        break

    lines.append(line)


text = "\n".join(lines)



# =====================================
# 1. Regex 탐지
# =====================================

regex_entities = detect_regex(text)



# =====================================
# 2. LLM 탐지
# =====================================

llm_entities = detect_llm(text)



# =====================================
# 3. Policy 적용 + 비식별화
# =====================================

final_text = apply_policy(
    text,
    regex_entities,
    llm_entities
)



# =====================================
# 결과 출력
# =====================================

print("\n" + "=" * 60)
print("원본")
print("=" * 60)

print(text)



print("\n" + "=" * 60)
print("Regex 탐지 결과")
print("=" * 60)

for entity in regex_entities:
    print(entity)



print("\n" + "=" * 60)
print("LLM 탐지 결과")
print("=" * 60)

for entity_type, values in llm_entities.items():

    print(f"\n[{entity_type}]")

    for entity in values:
        print(entity)



print("\n" + "=" * 60)
print("최종 비식별화 결과")
print("=" * 60)

print(final_text)