from app.regex_engine import detect_regex
from app.eeve_client import detect_llm
from app.actions.apply_policy import apply_policy

print("=" * 60)
print("개인정보 비식별화 테스트")
print("=" * 60)

print("\n문장을 입력하세요.")
print("입력 종료는 빈 줄(Enter 두 번)입니다.\n")

lines = []

while True:
    line = input()
    if line == "":
        break
    lines.append(line)

text = "\n".join(lines)

if not text.strip():
    print("\n입력된 문장이 없습니다. 종료합니다.")
    raise SystemExit(0)

regex_entities = detect_regex(text)

try:
    llm_entities = detect_llm(text)
except Exception as e:
    print(f"\n[경고] LLM 탐지 실패, LLM 결과 없이 진행합니다: {e}")
    llm_entities = {"PERSON": [], "ADDRESS": [], "ORGANIZATION": []}

result = apply_policy(
    original_text=text,
    regex_entities=regex_entities,
    llm_entities=llm_entities
)

print("\n" + "=" * 60)
print("원본")
print("=" * 60)
print(text)

print("\n" + "=" * 60)
print("Regex 탐지")
print("=" * 60)

if regex_entities:
    for entity in regex_entities:
        print(entity)
else:
    print("(탐지된 항목 없음)")

print("\n" + "=" * 60)
print("LLM 탐지")
print("=" * 60)

for entity_type, items in llm_entities.items():

    if not items:
        continue

    print(f"[{entity_type}]")

    for item in items:
        print(f"  {item}")

if not any(llm_entities.values()):
    print("(탐지된 항목 없음)")

print("\n" + "=" * 60)
print("최종 결과 - masked_text")
print("=" * 60)
print(result["masked_text"])

print("\n" + "=" * 60)
print("최종 결과 - rewritten_text")
print("=" * 60)
print(result["rewritten_text"])