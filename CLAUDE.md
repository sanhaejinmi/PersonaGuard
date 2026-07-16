# CLAUDE.md — PersonaGuard

이 문서는 Claude Code가 이 레포에서 작업할 때 반드시 따라야 하는 프로젝트 컨텍스트와 규칙이다.

## 1. 프로젝트 개요

PersonaGuard는 사용자가 ChatGPT에 입력하는 프롬프트를 입력 시점에 가로채, 개인정보를 탐지하고
사용자 협상을 거쳐 **원래 질문의 목적을 유지한 채** 비식별 문장으로 재작성한 뒤에만 외부로
전송하는 AI 보안 Agent이다.

- 목표: 2026 융합보안소프트웨어 경진대회 출품 (마감: 2026-08-12)
- 핵심 차별점: 단순 마스킹/차단이 아니라 **목적을 보존하는 재작성** + 사용자 선택(협상) 구조
- "Agent"는 시스템 전체를 가리키는 용어이다. 내부 구성요소는 Module이라고 부른다.
  (예: Negotiation Module, Rewrite Module — "OO Agent"라는 컴포넌트명 사용 금지)

## 2. 시스템 아키텍처 (3계층 + 외부)

### Client Layer — Chrome Extension (Manifest V3, JavaScript) — `extension/`
- Content Script: ChatGPT 입력창의 프롬프트 감지·가로채기, 최종 프롬프트 주입
- Result UI: 탐지 결과 표시, 항목별 마스킹 선택 UI
- Approval & Sender: 사용자 승인 후 재작성 프롬프트만 전송

### Application Layer — FastAPI (Python 3.11+) — `backend/`
- REST API Endpoint: `POST /analyze`, `POST /rewrite`
- Pipeline Controller: 모듈 실행 순서 제어 (`backend/app/pipeline.py`)
- Regex Engine: 정형 개인정보 탐지 (`regex_engine.py`)
- Masking Module: mask_rule 기반 placeholder 치환 (`masking.py`)
- Result Merger: Regex + EEVE 탐지 결과 병합 (`merger.py`)
- Negotiation Module: 사용자 제안 생성
- Session Store: 원본·위치 매핑 보관 (In-Memory, 세션 격리 필수)

### AI Layer — EEVE 로컬 서빙 (`eeve_client.py`)
- 단일 EEVE 모델, 프롬프트 템플릿으로 역할 분리. 프롬프트 1건당 총 2회 호출:
  - 1차 호출(탐색): 마스킹된 문장에서 문맥 기반 개인정보 탐지 → JSON 출력
  - 2차 호출(치환): 사용자 확정 항목을 비식별화하며 목적 유지 재작성

### External — ChatGPT (신뢰 경계 밖)
- 재작성·승인된 프롬프트만 전송된다. 원본은 절대 나가지 않는다.

## 3. 파이프라인 순서 (변경 시 아키텍처 리드 승인 필요)

① User Prompt 입력 (Extension)
② Regex Detection (value + start/end 위치 저장)
③ Masking — 정형 PII를 [PHONE], [EMAIL] 등 placeholder로 내부 치환
④ EEVE 1차 호출(탐색) — **입력은 반드시 ③의 마스킹본**
⑤ Detection Result 통합 (Python dict 병합, 키 충돌 없음)
⑥ Negotiation — 유형별 차등 제안 (아래 3.1)
⑦ User Decision — 항목 체크박스 선택 (Extension UI)
⑧ EEVE 2차 호출(재작성) — 확정 항목만 비식별화, 미선택 항목은 원문 유지
⑨ 사용자 승인 후 ChatGPT 전송 (Extension)

### 3.1 제안 정책 (2단계)
- Regex 탐지분(정형): 기본 마스킹 상태로 제시. 해제 시 경고.
- EEVE 탐지분(문맥): 기본 미체크, 사용자가 유지/마스킹 선택.
- 구현: 통합 JSON의 `source` 필드("regex" | "eeve")로 구분. 별도 분류 로직 만들지 말 것.

## 4. 데이터 계약

### 4.1 Regex Detection 결과
```json
{
  "PHONE": [{ "value": "010-2327-3450", "start": 54, "end": 67 }],
  "EMAIL": [{ "value": "kim@gmail.com", "start": 78, "end": 91 }]
}
```

### 4.2 EEVE 탐색 출력
```json
{
  "PERSON": ["김철수"],
  "ORGANIZATION": ["성신여자대학교"],
  "AFFILIATION": ["컴퓨터공학과 24학번"]
}
```

### 4.3 통합 Detection Result
- 4.1 + 4.2 병합 + 항목별 `source` 필드 추가.

### 4.4 오프셋 규칙 (중요)
- start/end는 **Python 기준 유니코드 코드포인트 인덱스**로 통일한다.
- Extension(JS)은 UTF-16 코드유닛 기준이므로, 하이라이트 표시 시 변환 함수를 거친다.
  이모지·특수문자 포함 테스트 케이스 필수.
- 치환은 **뒤에서 앞으로(오프셋 큰 것부터)** 수행한다. 앞에서부터 치환하면 이후 오프셋이 밀린다.

### 4.5 Placeholder 규칙
- 동일 타입 다중 출현 시 인덱싱: [PHONE_1], [PHONE_2]
- 세션별 매핑 테이블 {placeholder → (원본값, start, end)}를 Session Store에 유지.
- 사용자가 원문에 "[PHONE]" 문자열을 직접 쓴 경우와 구분할 것.

## 5. 보안 불변조건 (절대 규칙 — 위반 코드 작성 금지)

1. EEVE 탐색(④) 입력은 반드시 마스킹본이다. 원본 정형 PII를 LLM에 전달하는 코드 금지.
2. 원본 프롬프트·PII를 로그, print, 예외 메시지, 테스트 출력에 남기지 않는다.
3. `.env`, API 키, 모델 가중치 파일(*.gguf 등)은 커밋하지 않는다.
4. 외부(ChatGPT)로 나가는 것은 사용자가 승인한 재작성본뿐이다.
5. 정규식 작성 시 ReDoS 방지: 중첩 수량자 금지, 입력 길이 상한(50,000자), 매칭 타임아웃 적용.
6. Session Store는 요청 간 격리를 보장한다 (동시 요청에서 타인의 매핑 접근 불가).

## 6. Regex Engine 규칙

- 탐지 대상(1차 구현): 휴대폰번호, 이메일, 주민등록번호, API Key/Token
- 한국어 특성 처리: 조사 결합("~입니다"), 하이픈 유무, 공백 변형 대응
- 주민등록번호: 2020.10 이후 발급분은 뒷자리 무작위 → 구식 체크섬 검증 넣지 말 것 (날짜 유효성만)
- 모든 패턴은 `backend/tests/`의 골든 테스트셋(잡혀야 할 예시 / 잡히면 안 되는 예시)과 함께 추가한다.

## 7. 코딩 컨벤션

- Python 3.11+, FastAPI. 포매터: black + isort. 린터: ruff. 테스트: pytest.
- 타입 힌트 필수. 함수/변수명 영어, 주석·docstring 한국어 허용.
- 커밋 메시지: `feat:`, `fix:`, `test:`, `docs:` prefix (Conventional Commits 간소판)
- main 직접 푸시 금지. 기능 브랜치(`feat/...`) → PR → 리뷰 1인 이상 → 머지.
- Extension: Manifest V3 준수, 빌드 도구 없이 순수 JS로 시작 (필요 시 팀 논의 후 도입).

## 8. 확정/미확정 사항

### 확정
- Regex 직접 구현 (Presidio 미사용 — 1차 범위)
- User Decision = 항목 체크박스 방식 (후보 3개 선택 방식 아님)
- EEVE 2회 호출 (탐색 1 + 치환 1)
- 2단계 제안 정책 (source 기반)

### 미확정 (구현 전 팀 확인 필요 — 임의로 구현하지 말 것)
- EEVE 서빙 방식 (Ollama / vLLM / 기타)
- 자기검증 루프(재작성본 재탐지) 포함 여부와 재시도 횟수
- Session Store의 TTL·용량 정책
- 재작성 결과 표기 방식 (placeholder 유지 vs 가명 대체값)

## 9. Claude Code 작업 지침

- 새 모듈 추가 시 이 문서의 데이터 계약(§4)과 보안 불변조건(§5)을 먼저 확인한다.
- 파이프라인 순서(§3)나 데이터 계약(§4)을 바꾸는 변경은 코드만 고치지 말고
  이 문서도 같은 PR에서 갱신한다.
- 테스트 없는 탐지 패턴 추가 금지 (§6).
- 미확정 사항(§8)에 해당하는 기능은 구현 전에 사용자에게 확인을 요청한다.
