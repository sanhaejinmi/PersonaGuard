import json
import ollama


def detect_llm(prompt):
    system_prompt = """
당신은 개인정보 탐지 AI이다.

사용자가 입력한 문장에서 아래 개인정보만 찾아라.

탐지 대상
1. PERSON (사람 이름)
2. ADDRESS (주소)
3. ORGANIZATION (학교, 회사, 기관)

규칙
- JSON만 출력한다.
- 설명하지 않는다.
- Markdown(```json)을 출력하지 않는다.
- text만 출력한다.
- start, end는 출력하지 않는다.
- 없는 항목은 빈 리스트([])

출력 예시

{
    "PERSON":[
        {
            "text":"홍길동"
        }
    ],
    "ADDRESS":[
        {
            "text":"서울특별시 강남구"
        }
    ],
    "ORGANIZATION":[
        {
            "text":"서울대학교"
        }
    ]
}
"""

    response = ollama.chat(
        model="exaone3.5:2.4b",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    content = response["message"]["content"].strip()

    # Markdown 제거
    if content.startswith("```json"):
        content = content[len("```json"):]

    elif content.startswith("```"):
        content = content[len("```"):]

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    return json.loads(content)
    