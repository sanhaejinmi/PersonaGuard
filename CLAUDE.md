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
- REST API Endpoint: `POST /analyze`, `POST /rewrite` (둘 다 구현·연결 완료)
- Pipeline Controller: 모듈 실행 순서 제어 (`backend/app/pipeline.py`)
- Regex Engine: 정형 개인정보 탐지, `backend/app/regex/*.py` 하위 모듈을 취합
  (`regex_engine.py`) — 전화번호·이메일·주민등록번호·외국인등록번호·계좌·카드·
  사업자등록번호·여권번호·운전면허번호. `detect_regex(prompt)`는 **평탄한 리스트**
  `[{"type","value","start","end"}, ...]`를 반환한다 (§4.1 참고 — 타입별 dict 아님).
- Policy: 타입별 처리 정책 테이블 (`app/actions/policy.py::POLICY`) — 타입마다
  `"mask"`(구조화된 부분 마스킹) 또는 `"replace"`(자연스러운 가명 치환) 지정.
  현재 RRN/PHONE/DRIVER_LICENSE/BANK_ACCOUNT/CARD/PASSPORT/FOREIGNER_REGISTRATION/
  BUSINESS_NUMBER/PERSON은 `"mask"`, EMAIL/ADDRESS/ORGANIZATION은 `"replace"`.
- Masking: 구조화된 부분 마스킹 (`app/actions/masking.py::mask_value(value, type)`).
  타입별 전용 규칙이 있다 (RRN → `900101-1******`, PHONE → `010-12**-****` 등).
  PERSON은 `mask_value()`에 전용 규칙이 없어 `_generic_mask()`(앞 2글자 노출)로
  빠지므로, `pipeline.py`/`apply_policy.py` 둘 다 PERSON만은 `mask_value()`를
  거치지 않고 자체 `mask_person()`(첫 글자만 남기고 나머지 마스킹, 예: "홍길동" →
  `홍**`)을 쓴다 — 두 곳에 같은 함수가 중복 정의돼 있으니 한쪽을 고치면 다른
  쪽도 맞춰야 한다. 값 하나만 받아 치환값을 돌려주는 함수라, 텍스트 내 위치
  치환은 호출하는 쪽(pipeline.py)이 오프셋 기준으로 처리한다.
- Replace: 자연스러운 가명 치환. `app/replace/replace_email.py`(랜덤, 매 호출
  결과 다름), `replace_address.py`(시/도+시/군/구까지만 남기는 일반화, 예:
  "부산광역시 해운대구 우동 123" → "부산광역시 해운대구"), `replace_organization.py`
  (유형 유지 일반화, 예: "성신여자대학교 정보보호학과" → "OO대학교 OO학과").
  이미 시/도+구 수준으로 짧은 주소는 일반화해도 그대로 노출되니 주의.
- `app/rewrite/entity_filter.py::is_valid_person_name/is_valid_organization`로
  LLM이 직함·일반명사를 PERSON/ORGANIZATION으로 오탐지하는 문제(§2 AI Layer)를
  걸러낸다. `pipeline.py`와 `apply_policy.py` 둘 다 이 모듈을 공유해서 쓴다.
- `app/actions/apply_policy.py::apply_policy(text, regex_entities, llm_entities)`가
  탐지+정책+치환을 텍스트 전체에 한 번에 적용하는 자체 파이프라인을 갖고 있지만,
  **사용자의 항목별 결정(decisions)을 반영할 방법이 없다** (텍스트만 받음, 전부
  일괄 적용). 그래서 `pipeline.py`는 이 함수를 통째로 쓰지 않고, 내부의
  POLICY/mask_value/replace_* 조합을 항목 단위로 재사용해 사용자 결정을 반영한다
  (`pipeline.py::_replacement_for()`). `app/ai_pipeline.py`는 이 조합을 CLI로
  테스트해보는 참고용 스크립트이며 실서비스 경로(`/analyze`, `/rewrite`)에서는
  쓰지 않는다.
- Result Merger + Negotiation: 별도 파일이던 `merger.py`(비어 있음)와
  `negotiation.py`(삭제됨) 대신, 현재 `pipeline.py`가 통합·tier 분류·겹침
  정리(§3 ⑤)까지 맡고 있다.
- Session Store: 원본 프롬프트 + tier 포함 엔티티 목록 보관 (In-Memory, 세션 격리 필수, `session_store.py`)

### AI Layer — EEVE = Ollama 로컬 서빙 (§8 확정)
- 프롬프트 1건당 총 2회 호출 대상 함수가 분리되어 있다:
  - 1차 호출(탐색): `exaone_client.py::detect_llm(masked_text)` (구 `eeve_client.py`
    — 파일명 변경됨) — 모델 `exaone3.5:2.4b`. 마스킹된 문장에서 PERSON/ADDRESS/
    ORGANIZATION 탐지 → JSON 출력, `add_position()`으로 start/end도 같이 계산해서
    준다 (§4.2) — 단, 그 오프셋은 `masked_text` 기준이라 원본 프롬프트 오프셋과
    좌표계가 다르다. pipeline.py는 이 오프셋을 쓰지 않고 값(text)을 원본
    프롬프트에서 재검색한다.
  - 2차 호출(재작성): `app/rewrite/llm_polish.py::polish_with_llm()` — 모델
    `exaone3.5:7.8b`. §8이 확정한 `exaone3.5:2.4b`와 **다른 모델**이다 — 2.4b가
    "~써줘" 같은 요청문을 완성된 이메일/문서로 바꿔버리는 문제가 재현돼서
    7.8b로 실험적으로 바꾼 것이며, 팀 확인 전까지는 §8 미확정으로 취급한다
    (로컬에 7.8b가 없으면 예외를 잡아 원문을 그대로 반환하도록 폴백돼 있어
    크래시는 안 남).
- `app/replace/replace_client.py::replace_personal_info(text, entities)` — 원본
  전체를 한 번에 치환하는 방식이라 **아직 pipeline에서 사용하지 않음**, §3.1
  하단 "알려진 제약" 참고.
- `app/rewrite/` 패키지에 "목적 보존 재작성"의 더 큰 실험적 구현이 있다
  (`purpose.py`=목적 추론, `necessity.py`=항목별 필요성 판단, `action.py`=필요성
  기반 keep/generalize/delete 결정, `purpose_flow.py`=이 전부를 묶은 독립
  파이프라인). **`purpose_flow.py` 자체(독립 파이프라인)는 여전히 pipeline.py에
  연결돼 있지 않지만, 그 안의 `infer_purpose()`/`classify_necessity()`/
  `decide_action()` 세 함수는 pipeline.py가 가져와서 "체크박스 기본값 제안"에만
  쓴다** (§3.1, `Entity.default_masked`) — 팀 결정(완전 대체 아님, 기본값
  제안으로만 사용): PERSON/PHONE 등은 그대로 항상 기본 마스킹, ADDRESS/
  ORGANIZATION만 목적 필요성으로 기본값이 갈린다. 사용자는 체크박스로 이
  기본값을 언제든 뒤집을 수 있다. 모델은 exaone3.5:7.8b라 §8 미확정 사항과 겹침.
- **알려진 이슈**: exaone3.5:2.4b가 "제 번호", "주민번호" 같은 일반 명사를 PERSON으로
  오탐지하는 사례를 확인했다 (실제 이름이 아닌데도 탐지). ORGANIZATION 쪽은 "팀장,
  과장, 교수(-님 포함)" 같은 직함을 `entity_filter.py`로 걸러내도록 개선됐지만,
  PERSON 오탐지는 아직 완전히 해결되지 않음 — AI 담당자 확인 필요.
- **알려진 버그**: `exaone_client.py::add_position()`이 모델이 `{"text": "..."}`
  형식 대신 문자열만 반환하는 경우(exaone3.5:2.4b가 가끔 이렇게 응답 — 실측
  약 1/3 빈도)를 방어하지 못하고 `AttributeError`로 크래시한다. `pipeline.py`는
  `detect_llm()` 호출을 try/except로 감싸서 실패 시 "이번엔 LLM 탐지 없음"으로
  조용히 넘어가게 방어해뒀지만(§3 ④), 근본 수정은 `exaone_client.py` 쪽에서
  필요함 — AI 담당자 확인 필요.

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
⑧ EEVE 2차 호출(재작성) — 확정 항목만 비식별화, 미선택 항목은 원문 유지.
   치환 후 `polish_with_llm()`으로 자연스럽게 다듬고 `self_check_rewrite()`로
   재탐지 — 문제 있으면 1회만 재시도 후 결과를 그대로 반환 (§8 확정)
⑨ 사용자 승인 후 ChatGPT 전송 (Extension)

### 3.1 탐지 프로파일 및 제안 정책 (Entity.tier 기반, 실제 구현 반영)

| Tier | 구분 | 탐지 항목(실제 구현) | 탐지 방식 | 처리 정책 |
|---|---|---|---|---|
| 1 | 고유식별정보 | RRN(주민등록번호), PASSPORT(여권번호), DRIVER_LICENSE(운전면허번호) | 정규식(regex) | **강제 마스킹 — 유지 선택 불가** (개인정보보호법 시행령 제19조) |
| 2 | 연락·계정정보 | PHONE, EMAIL, BANK_ACCOUNT, CARD, BUSINESS_NUMBER | 정규식(regex) | 기본 마스킹, 해제 시 경고 |
| 3 | 생활 문맥정보 | PERSON, ADDRESS, ORGANIZATION | LLM 문맥 탐지(eeve, `detect_llm`) | 기본 마스킹 후 사용자 선택(자기결정) |

- `Entity.tier`(int)로 백엔드가 직접 분류해서 내려준다 — Extension은 `entity.tier`가 있으면 그걸 우선 쓰고, 없을 때만 자체 `FORCED_MASK_TYPES` 표로 판단하도록 이미 구현돼 있다 (`extension/approval_sender.js`).
- Tier 1은 클라이언트가 체크박스를 막는 것과 별개로, **`pipeline.run_rewrite()`가 사용자 결정과 무관하게 항상 마스킹을 강제**한다 (§5 — 클라이언트만 신뢰하지 않는다).
- `Entity.default_masked`(bool) — 체크박스 **기본 제안값** (팀 확정, §8). Tier1/PERSON/PHONE 등은 항상 `true`. ADDRESS/ORGANIZATION만 `app/rewrite/purpose.py::infer_purpose()` + `necessity.py::classify_necessity()`로 "이 정보가 프롬프트 목적에 필요한가"를 판단해 필요하면 `false`(유지 제안)로 내려준다 — 예전에 검토했던 "질문 필수정보" 개념이 새 tier로 분리되는 대신 **같은 Tier3 안에서 항목별 기본값 제안**으로 구현됐다. 사용자는 여전히 체크박스로 이 기본값을 뒤집을 수 있다(§2 AI Layer, `pipeline.py::_assign_default_masked()`).
- **알려진 제약(재작성 ⑧ 관련)**: `apply_policy()`/`replace_client.py::replace_personal_info()`는 원본 전체를 한 번에 처리해서 사용자의 항목별 결정(decisions)을 반영할 방법이 없다. 그래서 `pipeline.run_rewrite()`는 이 함수들을 통째로 쓰지 않고, 같은 POLICY/mask_value/replace_*를 항목 단위로 재사용해(`_replacement_for()`) 확정 항목만 치환하고 미선택 항목은 원문을 유지한다.
- **패턴 겹침 수정됨**: `regex/business_number.py`의 패턴에 단어 경계(`\b`)가 없어서 주민등록번호 안의 일부 문자열이 BUSINESS_NUMBER로 같이 잡히던 문제를, 정규식 담당자가 `regex_engine.py::detect_regex()` 자체에 겹침 정리 로직(범용 `_is_overlapping()` — 특정 타입 하드코딩 없이 모든 겹치는 쌍에 적용)으로 해결했다. `pipeline.py`는 그 위에 regex 탐지분과 LLM 탐지분 **사이**에 생길 수 있는 겹침까지 한 번 더 정리한다 (`_dedupe_overlaps()`). 단, `business_number.py`/`bank_account.py`의 패턴 자체(단어 경계 없음)는 아직 그대로라 — 다른 상황에서 또 겹칠 수 있으니 새 패턴 추가 시 계속 확인할 것.

## 4. 데이터 계약

### 4.1 Regex Detection 결과 (실제 구현 — 평탄한 리스트, 타입별 dict 아님)
```json
[
  { "type": "PHONE", "value": "010-2327-3450", "start": 54, "end": 67 },
  { "type": "EMAIL", "value": "kim@gmail.com", "start": 78, "end": 91 }
]
```
`regex_engine.py::detect_regex(prompt)`가 이 형태로 반환한다.

### 4.2 EEVE 탐색 출력 (실제 구현)
```json
{
  "PERSON": [{ "text": "김철수", "start": 3, "end": 6 }],
  "ADDRESS": [{ "text": "서울특별시 강남구", "start": 10, "end": 19 }],
  "ORGANIZATION": [{ "text": "성신여자대학교", "start": 22, "end": 29 }]
}
```
`exaone_client.py::detect_llm(masked_text)`가 이 형태로 반환한다. `start`/`end`는
`add_position()`이 계산해서 붙여주지만, 이건 **detect_llm에 넘긴 텍스트(마스킹본)
기준** 오프셋이라 원본 프롬프트 오프셋과 좌표계가 다르다 — pipeline.py는 이
오프셋을 쓰지 않고 원본 프롬프트에서 값(text)을 재검색해 위치를 구한다.
값이 여러 번 등장하면 전부 별도 항목으로 잡는다 (마스킹 누락 방지 우선).

### 4.3 통합 Detection Result
- 4.1 + 4.2를 오프셋 기준으로 병합하고, 겹치는 span은 정리한다(§3.1 "알려진 버그" 참고).
- 최종적으로 `Entity(type, value, start, end, tier, default_masked)` 리스트가 되어 `AnalyzeResponse.entities`로 나간다.
- `AnalyzeResponse.candidates`는 `entities`와 **동일 인덱스로 매칭되는 치환 미리보기 문자열**
  리스트다 — POLICY 기준 실제 치환값이 들어간다 (예: PHONE이면 `"010-12**-****"`
  같은 부분 마스킹, ORGANIZATION이면 `"[기관]"`). 후보 3개 선택 방식이 아니라,
  Extension 협상 화면에서 항목별 "AI 제안"을 보여주기 위한 용도다. EMAIL 치환은
  랜덤이라 `/analyze`를 다시 호출하면 값이 바뀐다.

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

- 탐지 대상(구현 완료, `backend/app/regex/`): 전화번호(phone), 이메일(email),
  주민등록번호(rrn), 외국인등록번호(foreigner_registration), 계좌번호(bank_account),
  카드번호(card), 사업자등록번호(business_number), 여권번호(passport),
  운전면허번호(driver_license)
- 한국어 특성 처리: 조사 결합("~입니다"), 하이픈 유무, 공백 변형 대응
- 주민등록번호: 2020.10 이후 발급분은 뒷자리 무작위 → 구식 체크섬 검증 넣지 말 것 (날짜 유효성만).
  `rrn.py`/`business_number.py`에 체크섬 검증 함수가 있지만 실제 탐지에는 사용하지 않음 — 유지.
- **패턴 겹침 주의**: `business_number.py` 패턴에 단어 경계가 없어 RRN 안의 부분 문자열이
  BUSINESS_NUMBER로 같이 잡히던 문제는 `detect_regex()`의 자체 겹침 정리 로직(RRN 우선
  처리)으로 해결됨 (§3.1). 다만 패턴 자체는 여전히 느슨해서, 새 패턴 추가 시 기존
  패턴과의 겹침을 반드시 함께 확인할 것.
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
- 3단계 탐지 프로파일 정책, `Entity.tier` 필드로 백엔드가 직접 분류 (§3.1)
- EEVE 서빙 방식 = **Ollama**, 탐지 모델 = **exaone3.5:2.4b** (로컬 설치·pull 완료, 실제 동작 확인됨)
- `POST /analyze`, `POST /rewrite` 둘 다 구현·연결 완료. `AnalyzeResponse.session_id` 노출됨.
- 자기검증 루프 — `self_check_rewrite()`로 재작성본을 재탐지하고, 문제가 남아있으면
  **1회만 재시도**한 뒤 그 결과를 그대로 반환한다 (무한 재시도 없음). `pipeline.py`에
  연결 완료.
- PERSON 마스킹 — `mask_person()`(첫 글자만 남기고 나머지 마스킹)으로 개선 완료.
- ADDRESS/ORGANIZATION 치환 — `replace_address()`/`replace_organization()`으로
  일반화된 자연스러운 표현을 만들도록 개선 완료 (고정 라벨 `[주소]`/`[기관]` 대신).
- "질문 필수정보" 판단 — **완전 대체가 아니라 체크박스 기본값 제안으로 통합
  (팀 확정)**. `Entity.default_masked` 필드로 노출되고, ADDRESS/ORGANIZATION만
  목적 필요성 판단의 영향을 받는다 (§3.1). 사용자 체크박스 결정 UX는 그대로 유지.

### 미확정 (구현 전 팀 확인 필요 — 임의로 구현하지 말 것)
- 재작성(⑧) 다듬기 단계 및 필요성 판단(`default_masked`)에 쓰는 모델 — 지금
  `polish_with_llm()`/`infer_purpose()`/`classify_necessity()` 전부 §8 확정
  모델(2.4b)이 아니라 **exaone3.5:7.8b**를 쓴다 (2.4b가 요청문을 완성된 문서로
  바꿔버리는 문제 때문에 실험적으로 교체). 이 모델을 실서비스 확정으로 승인할지,
  로컬에 7.8b를 항상 pull해두는 걸 전제로 할지 팀 확인 필요. (7.8b가 없어도
  각 함수가 예외를 잡아 안전한 기본값으로 폴백하므로 크래시는 안 남.)
- Session Store의 TTL·용량 정책
- `regex/business_number.py`, `regex/bank_account.py` 패턴 자체의 word boundary 보강
  (겹침 증상은 `detect_regex()` 후처리로 해결됐지만 패턴 근본 수정은 아직, §6)
- `exaone_client.py::add_position()`의 모델 출력 형식 방어 (§2 AI Layer "알려진 버그")

## 9. Claude Code 작업 지침

- 새 모듈 추가 시 이 문서의 데이터 계약(§4)과 보안 불변조건(§5)을 먼저 확인한다.
- 파이프라인 순서(§3)나 데이터 계약(§4)을 바꾸는 변경은 코드만 고치지 말고
  이 문서도 같은 PR에서 갱신한다.
- 테스트 없는 탐지 패턴 추가 금지 (§6).
- 미확정 사항(§8)에 해당하는 기능은 구현 전에 사용자에게 확인을 요청한다.
