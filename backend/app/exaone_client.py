import json
import ollama


def add_position(prompt, entities):
    """
    LLM 탐지 결과에 start/end 위치 추가
    - 같은 텍스트가 여러 번 등장하면 모든 위치를 각각 엔티티로 추가한다
    - LLM이 같은 텍스트를 중복 반환해도 한 번만 처리한다
    - exaone3.5:2.4b가 가끔 {"text": "..."} 대신 문자열을 그대로 리스트에
      담아 반환하는 경우가 있어(3회 중 1회꼴로 재현, /analyze 500 에러의
      원인이었음), 항목이 dict가 아니거나 entities 자체가 예상한 구조가
      아니어도 죽지 않도록 방어한다.
    """

    result = {}

    if not isinstance(entities, dict):
        return result

    for entity_type, items in entities.items():

        result[entity_type] = []

        if not isinstance(items, list):
            continue

        seen_texts = set()

        for item in items:

            if isinstance(item, dict):
                text = item.get("text")
            elif isinstance(item, str):
                text = item
            else:
                continue

            if not text:
                continue

            if text in seen_texts:
                continue

            seen_texts.add(text)

            start = 0

            while True:

                found = prompt.find(text, start)

                if found == -1:
                    break

                result[entity_type].append(
                    {
                        "text": text,
                        "start": found,
                        "end": found + len(text)
                    }
                )

                start = found + len(text)

    return result


def detect_llm(prompt):

    system_prompt = """
당신은 개인정보 탐지 AI이다.

사용자의 문장에서 아래 개인정보를 모두 찾아라.

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
- 문장에 등장하는 모든 개인정보를 반환한다.
- 같은 종류가 여러 개 있으면 모두 반환한다.
- 절대 하나만 반환하지 않는다.
- ORGANIZAION에서 다음의 명칭은 탐지 하지 않는다.
예) "팀장, 과장, 교수, 학생, 대리, 주무관, 상사, 하사"

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
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    )

    content = response["message"]["content"].strip()

    if content.startswith("```json"):
        content = content[len("```json"):]
    elif content.startswith("```"):
        content = content[len("```"):]

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        result = {"PERSON": [], "ADDRESS": [], "ORGANIZATION": []}

    result = add_position(prompt, result)

    return result