from app.regex_engine import detect_regex
from app.eeve_client import detect_llm
from app.actions.apply_policy import apply_policy

# 코딩 테스트용

print("=" * 60)
print("개인정보 비식별화 테스트")
print("=" * 60)


# 사용자 입력
text = input("\n문장을 입력하세요:\n\n")



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

print("Regex")
print("=" * 60)

print(regex_entities)



print("\n" + "=" * 60)

print("LLM")
print("=" * 60)

print(llm_entities)



print("\n" + "=" * 60)

print("최종")
print("=" * 60)

print(final_text)