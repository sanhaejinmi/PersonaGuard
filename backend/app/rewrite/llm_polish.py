import re

import ollama

SYSTEM_PROMPT = """
당신은 문장에서 비식별화 안내 문구를 제거하고 자연스럽게 다듬는 AI입니다.

[규칙]
1. 입력 문장의 의미를 절대 바꾸지 않는다.
2. 문장 종류를 바꾸지 않는다.
   - 요청문은 요청문으로 유지한다.
   - 평서문은 평서문으로 유지한다.
3. 어투를 바꾸지 않는다.
   - 구어체는 구어체로 유지한다.
   - "~인데" 를 "~이시군요" 로 바꾸지 않는다.
4. (연락처 비식별화), (이메일 비식별화), (기관 비식별화), (주소 비식별화),
   (비식별화) 같은 안내 문구와 그 앞 항목명(이메일, 계좌번호, 소속 등)을
   문장에서 완전히 제거한다.
   예) "이메일은 (이메일 비식별화)이고" → 통째로 제거
   예) "계좌번호는 (비식별화)인데" → 통째로 제거
   예) "(연락처 비식별화)로 담당자한테" → "(연락처 비식별화)로" 만 제거
   예) "(기관 비식별화) 소속인데" → 통째로 제거
   예) "(주소 비식별화)에 살고 있는데" → 통째로 제거
5. 안내 문구를 지운 뒤, 그것 때문에 의미가 없어진 서술이 남으면 그 서술도
   함께 제거한다.
   예) 연락처를 지웠는데 "연락 가능합니다"만 남으면 → 그 서술도 제거
   예) 주소를 지웠는데 "거기 살고 있어요"만 남으면 → 그 서술도 제거
6. 숫자+별표/X 형태의 마스킹 값(900101-1******, 1234-XXXX-XXXX-3456 등)은
   그대로 유지한다.
7. 요청 표현은 아래 기준으로만 통일한다.
   "써줘", "써라", "만들어줘" → "작성해줘"
   "해줘", "해라", "해봐" → "해줘"
8. 새로운 정보를 추가하지 않는다.
9. Markdown을 사용하지 않는다.
10. 다듬은 문장만 출력한다.
11. "목적"이 함께 주어지면, 그건 이 문장이 최종적으로 무엇을 하려는 건지
    참고하라는 것이지 문장에 그대로 옮기라는 게 아니다. 목적 문구 자체를
    출력에 넣지 않는다.
12. 당신은 이 문장에 답변하거나 요청을 수행하는 게 아니다 — 문장 자체를
    다듬는 편집자다. "~써줘", "~해줘" 같은 요청 표현을 "~해드리겠습니다"
    같은 응답/완료 표현으로 절대 바꾸지 않는다.

[예시]
입력: OO회사 인턴입니다. 이메일은 (이메일 비식별화)이고 계좌번호는 (비식별화)인데, 인사팀에 급여 문의 이메일 써줘
출력: OO회사 인턴입니다. 인사팀에 급여 문의 이메일 작성해줘

입력: OO기관 소속인데, (연락처 비식별화)로 담당자한테 환불 신청 문자 메시지 써줘
출력: OO기관 소속인데, 담당자한테 환불 신청 문자 메시지 작성해줘

입력: OO대학교 학생인데, 교수님한테 (이메일 비식별화)로 과제 연장 부탁하는 이메일 써줘
출력: OO대학교 학생인데, 교수님한테 과제 연장 부탁하는 이메일 작성해줘

입력: 오늘 병원 가야해서 (연락처 비식별화)로 팀장님한테 반차 쓴다고 문자 메시지 써줘
출력: 오늘 병원 가야해서 팀장님한테 반차 쓴다고 문자 메시지 작성해줘

입력: 서울특별시 강남구 살고 있고, 주민번호는 900101-1******이야, 개인정보 처리 동의서 내용 정리해줘
출력: 서울특별시 강남구 살고 있고, 주민번호는 900101-1******이야, 개인정보 처리 동의서 내용 정리해줘

입력: (기관 비식별화) 소속인데, 인사팀에 재직증명서 발급 요청 이메일 써줘
출력: 인사팀에 재직증명서 발급 요청 이메일 작성해줘

입력: (주소 비식별화)에 사는데, 근처 이사업체 좀 추천해줘
출력: 근처 이사업체 좀 추천해줘

입력: 성신여자대학교 학생인데 로 연락 가능합니다. 교수님께 결석계 이메일 좀 작성해줘
출력: 성신여자대학교 학생인데 교수님께 결석계 이메일 좀 작성해줘
"""


def _strip_markdown_fence(text: str) -> str:

    text = text.strip()

    if text.startswith("```"):

        lines = text.split("\n")

        if lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    return text


_OUTPUT_LABEL_PATTERN = re.compile(r"^\s*출력\s*[:：]\s*")


def _strip_output_label(text: str) -> str:
    """모델이 user_prompt의 '출력:' 라벨을 그대로 따라 쓰는 경우가 있어 제거한다."""
    return _OUTPUT_LABEL_PATTERN.sub("", text, count=1).strip()


def polish_with_llm(cleaned_text: str, purpose: str = "") -> str:
    """전처리(person/contact_label/org_address_label/label_strip)를 거친 문장을
    마지막으로 다듬는다.

    exaone3.5:7.8b 사용 — CLAUDE.md §8이 확정한 exaone3.5:2.4b와 다르다.
    2.4b가 요청문을 완성된 이메일/문서로 바꿔버리는 문제(예: "~써줘" → 가짜
    이메일 초안 전체 생성)가 실제로 재현돼서 7.8b로 바꿨다 — 이 함수는
    orchestrator.py(기존 타입 기반 흐름)와도 공유되므로, 그쪽 호출도 함께
    영향을 받는다. 실제 서비스 확정 모델을 바꾸는 결정은 아니고, 팀 확인 전
    실험적 오버라이드다.

    purpose: purpose_flow.py의 STEP1에서 구한 목적 요약(선택). 주어지면 모델이
    "이 문장이 결국 뭘 하려는 건지" 참고할 수 있게 컨텍스트로만 넘긴다 — 그대로
    출력에 옮기지 않도록 SYSTEM_PROMPT 규칙 11에서 명시한다. orchestrator.py는
    purpose 개념이 없으므로 기본값("")으로 그대로 호출한다.
    """

    if not cleaned_text or not cleaned_text.strip():
        return cleaned_text

    if purpose:
        user_prompt = f"""
목적: {purpose}
입력: {cleaned_text}
출력:"""
    else:
        user_prompt = f"""
입력: {cleaned_text}
출력:"""

    try:

        response = ollama.chat(
            model="exaone3.5:7.8b",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            options={
                "temperature": 0.1,
                "top_p": 0.2
            }
        )

        rewritten = response["message"]["content"].strip()
        rewritten = _strip_markdown_fence(rewritten)
        rewritten = _strip_output_label(rewritten)

        if not rewritten:
            return cleaned_text

        return rewritten

    except Exception as e:

        print(f"[Rewrite Error] {e}")
        return cleaned_text
