# 변경 정리 — AI 구조 재구성 (`f9457de` → `4dccd79`)

- 작업자: bess
- 대상 커밋: `f9457de`(eeve→exaone 리네이밍), `4dccd79`("ai 구조 재구성")
- 브랜치: su → develop 머지

> **2026-08-04 갱신**: 아래 "미연동" 서술은 `f9457de`/`4dccd79` 시점(2026-07-28) 기준이다.
> 그 뒤 develop/su 브랜치에 추가로 들어온 커밋들이 `app/rewrite/`의 일부 함수를
> `pipeline.py`에 실제로 연결했다. 최신 연동 상태는 [§5](#5-2026-08-04-pull-이후-갱신된-연동-상태--새로-발견된-문제)
> 참고.

## 배경

메모리([[project-purpose-aware-rewrite-flow]])에 남아있던 대로, "목적 보존 재작성(STEP1-5)" 흐름은
**설계만 승인되고 실제 구현은 보류**된 상태였다. 이번 커밋에서 bess가 이걸 실제로 코드로 구현했는데,
**`pipeline.py`/`main.py`에는 연결하지 않고 완전히 독립된 실험 모듈로 격리**해뒀다. 각 파일 docstring에
"아직 미연동"이라고 명시돼 있어서, 당시(2026-07-28) 실서비스 경로(`/analyze`, `/rewrite`)는 기존 로직
그대로 동작했다 — 이후 상태는 §5 참고.

---

## 1. 사소한 변경 — exaone 리네이밍

- `app/eeve_client.py` → `app/exaone_client.py` (파일명만 변경, 내용 동일)
- `pipeline.py`: import 한 줄만 `eeve_client` → `exaone_client`로 교체. **로직은 전혀 안 건드림.**
- `main.py`: import 방식 정리 + `/rewrite` 엔드포인트의 예외 처리를 살짝 리팩터링(같은 동작 유지).
  `analyze_service()`라는 얇은 wrapper 함수 하나 추가.

## 2. 핵심 변경 — `app/rewrite/` 패키지 신설

### 2-1. 기존 `rewrite_masked_prompt.py` 리팩터링 (254줄 → 타입별 모듈 분리)

원래 한 파일에 person/전화번호/이메일/라벨 정리 로직이 다 섞여 있던 걸, 아래처럼 쪼갰다.

| 파일 | 역할 |
|---|---|
| `person.py` | 마스킹된 이름(`이**`) 또는 원본 이름 언급 제거, 뒤 조사까지 함께 정리 |
| `contact_label.py` | 부분마스킹된 전화번호/이메일 → `(연락처 비식별화)` / `(이메일 비식별화)` 공통 포맷으로 변환 |
| `org_address_label.py` | `[기관]`/`[주소]` 고정 라벨 → `(기관 비식별화)` / `(주소 비식별화)` 포맷으로 변환 |
| `label_strip.py` | 안내 문구 + **앞의 항목명**(예: "이메일은")까지 통째로 제거. 정규식 조사 순서 버그(그리디 매칭으로 "이고"의 "이"만 지워지고 "고"가 남던 문제) 수정 |
| `llm_polish.py` | 최종적으로 exaone에 던져서 자연스럽게 다듬는 단계 |
| `orchestrator.py` | 위 5단계를 순서대로 실행하는 조립 함수 (`rewrite_masked_prompt`) |

`rewrite_masked_prompt.py`는 이제 `orchestrator.rewrite_masked_prompt`를 그대로 재노출하는
**하위 호환용 껍데기**로만 남았다 — `apply_policy.py` 등 기존 코드가 깨지지 않게.

### 2-2. 신규 — STEP1~5 목적 보존 재작성 흐름 (`purpose_flow.py` 중심)

```
STEP1 목적 추론 (purpose.py)
   ↓
STEP2-3 항목별 필요/불필요 판단 (necessity.py)
   ↓
STEP4 타입별 행동 결정 (action.py) — keep / generalize / delete
   ↓
STEP5 목적을 컨텍스트로 넘겨 최종 문장 생성 (llm_polish.py 재사용)
```

- **`purpose.py`**: 프롬프트 전체 목적을 한 문장으로 요약 (`{"purpose": "..."}`).
- **`necessity.py`**: 목적 + 엔티티 값 목록을 주고 `{값: true/false}`로 필요성 판단.
- **`action.py`**: 타입별 규칙표.
  - PERSON → 항상 `generalize`(일반화)
  - PHONE/EMAIL/계좌/카드/RRN/여권/운전면허/외국인등록/사업자등록/학번 → 항상 `delete`
  - ORGANIZATION/ADDRESS → 필요성 판단 결과에 따라 `keep`/`delete`
- **`entity_filter.py`**: exaone이 "제 번호", "교수님" 같은 일반명사/직함을 PERSON·ORGANIZATION으로
  오탐지하는 기존 문제(CLAUDE.md §2)에 대한 필터를 개선 — 기존엔 "교수"만 블랙리스트에 있어서
  "교수님"(경어체 "-님" 붙은 형태)은 못 걸렀는데, 이번에 그 케이스를 추가로 잡도록 함. `apply_policy.py`도
  이 필터를 재사용하도록 정리해서 중복 로직 제거.
- **`purpose_flow.py`**: 위 단계를 실제로 엮는 오케스트레이터(`rewrite_with_purpose`). 이 커밋(2026-07-28)
  시점에는 완전히 독립적이었지만, **§5에 정리된 이후 pull에서 `purpose.py`/`necessity.py`/`action.py`
  세 함수만 개별적으로 `pipeline.py`에 재사용되기 시작했다** — `purpose_flow.py` 자체(오케스트레이터)는
  여전히 pipeline.py에 연결돼 있지 않다.

#### 발견 → 수정된 버그 (50개 프롬프트 실험 기반)

1. **목적 추론에 PII가 새는 문제**: 처음엔 정규식으로 마스킹한 텍스트만 STEP1(목적 추론)에 넘겼더니,
   PERSON/ORGANIZATION/ADDRESS는 아직 원문 그대로 남아있어서 "신동엽 원장" 같은 이름이 `purpose`
   문자열에 그대로 요약되고, 그 `purpose`가 다시 STEP5 컨텍스트로 전달되면서 **이미 지웠어야 할 PII가
   최종 결과물에 재노출**되는 사례가 있었다. → 목적 추론 전용으로 정규식+LLM 탐지 엔티티를 전부
   마스킹한 텍스트(`_mask_all_entities`)를 따로 만들어 해결.
2. **대괄호 자리표시자 잔존**: `[ORGANIZATION]` 같은 내부용 토큰이 purpose 요약이나 모델이 지어낸
   빈칸(`[이름]`, `[연락처]`)으로 최종 결과에 남는 경우가 있어, `_strip_bracket_placeholders()`로
   purpose·최종 결과 양쪽에 안전망 추가.
3. **삭제 대상 라벨을 LLM에 맡기면 안 되는 타입들**: RRN/여권/운전면허/외국인등록/사업자등록/계좌/카드
   같은 Tier1/2 타입은 라벨을 LLM(`llm_polish`)에 그대로 넘기면 "~는 비식별화되었습니다" 같은
   **설명문으로 바꿔버리는** 문제가 반복 재현됨 (프롬프트에 정확히 일치하는 예시를 넣어도 안 고쳐짐 —
   작은 모델 한계로 판단). → 이 타입들은 `strip_mechanical_only_labels()`로 LLM 안 거치고 정규식으로
   기계적으로 삭제. 반대로 PHONE/EMAIL/ORGANIZATION/ADDRESS는 라벨을 LLM에 그대로 넘겨야 앞
   항목명("계좌번호는" 등)까지 자연스럽게 같이 지워지는 걸 확인해서 그대로 둠.
4. **잔여 안내문구 안전망**: LLM이 안내 문구를 못 지우고 그대로 남기는 경우가 실제로 재현돼서
   (같은 입력도 매번 완벽히 처리되진 않음), `strip_residual_disclosure_phrase()`로 최종 출력에
   한 번 더 안전망 적용.

#### 시도했다가 롤백한 것 — `layers/` 체이닝 구조

2026-07-29에 person/organization/address를 **각각 독립된 LLM 호출로 체이닝**
(`app/rewrite/layers/`: `person_layer.py`, `organization_layer.py`, `address_layer.py`,
`contact_and_id_layer.py`, `_layer_base.py`)하는 구조를 시도했으나, **exaone3.5:2.4b(작은 모델)로
실제 테스트해보니 호출을 체이닝할수록 드리프트가 누적**됐다.

- "~써줘" 같은 요청문이 "~해드리겠습니다" 같은 응답문으로 바뀜
- 없던 직함을 지어냄
- 프롬프트를 강화해도 재현되는 심각한 문제

→ **STEP5는 다시 단일 `llm_polish.polish_with_llm()` 호출로 되돌림.** 대신 STEP1에서 구한 `purpose`를
컨텍스트로 함께 넘겨서("목적을 재작성 단계까지 가져가면 더 정확해질 것"이라는 원래 의도는 최소 변경으로
유지). `layers/` 코드 자체는 지우지 않고 남겨뒀지만 **이 흐름에서는 쓰이지 않는다** (죽은 코드 상태).

### 2-3. 신규 — `self_check.py` (자기검증, CLAUDE.md §8 확정 항목)

재작성본을 다시 탐지해서 PII/안내문구 잔존 여부를 체크하는 모듈. **재탐지된 값 자체는 반환하지 않고
타입별 개수만** 반환한다(§5.2 — 원본/PII를 로그·예외에 남기지 않는 규칙 준수). 문제 없으면 `None`,
있으면 `SelfCheckResult(total, by_type)`. **재시도 로직은 없음(이 모듈 자체는)** — 탐지·보고까지만 담당.
이 커밋 시점엔 미연동이었지만, **§5에서 정리된 이후 pull에서 `pipeline.py::run_rewrite()`가 이 함수를
호출해 재시도(최대 1회) 로직을 pipeline.py 쪽에서 직접 구현·연결했다.**

---

## 3. 주의가 필요한 부분 (팀 확인 권장)

1. **`necessity.py`, `purpose.py`, `llm_polish.py` 전부 `exaone3.5:7.8b`를 씀** — CLAUDE.md §8이 확정한
   모델은 `exaone3.5:2.4b`다. 세 파일 모두 주석으로 "2.4b가 요청문을 완성된 문서/이메일로 바꿔버리는
   문제가 재현돼서 7.8b로 실험 중, 실제 서비스 확정 모델을 바꾸는 결정은 아님"이라고 명시는 해뒀지만,
   **`llm_polish.py`는 기존 `orchestrator.py`(현재 rewrite 흐름)와도 공유되는 함수**라서 이 부분은 기존
   확정 경로에도 영향이 있을 수 있다. 실제로 `main.py`→`pipeline.py` 경로가 이 `llm_polish`를 타는지는
   확인 필요.
2. `layers/` 디렉터리는 실험 후 롤백된 죽은 코드로, 유지할지 삭제할지 팀 논의 필요.
3. ~~`purpose_flow.py`/`self_check.py` 모두 "아직 pipeline.py에 미연동"~~ → **§5 참고, 이후 pull로 대부분
   연동 완료됨.**

## 4. 테스트/실험 자산

- `test_rewrite_*.py` 8종 신규 추가 (action, entity_filter, label_strip, layers, llm_polish, org_address,
  purpose_flow, self_check)
- `backend/scripts/`에 50개 프롬프트 배치 실험 스크립트 + 결과 파일(`results_50_*.txt`) 다수 추가 —
  위에서 언급한 버그들을 찾아낸 실험 근거 자료로 보임.
- 구 `ai_function.py`(171줄), `test_ai_pipeline.py`, `test_llm.py` 삭제.

---

## 5. 2026-08-04 pull 이후 갱신된 연동 상태 + 새로 발견된 문제

`su` 브랜치가 develop 쪽 커밋들을 새로 pull 받으면서 `pipeline.py`(+128줄), `schemas.py`(+1줄),
`extension/*` 여러 파일이 갱신됐다. `pipeline.py`/`extension/`은 다른 팀원 소유라 이 문서 갱신 외에
코드는 건드리지 않았고, 아래는 diff를 읽고 확인한 내용이다.

### 5-1. §2/§3에서 "미연동"이라던 것들이 실제로 연동됨

- **`self_check.py` 연동**: `pipeline.py::run_rewrite()`가 재작성 후 `self_check_rewrite()`로 재탐지하고,
  문제가 남아있으면 **`polish_with_llm()`을 한 번만 더 호출(재시도)**한 뒤 그 결과를 그대로 반환한다
  (무한 재시도 없음 — CLAUDE.md §8 확정 사항이 됨).
- **`purpose_flow.py`의 부품 3개만 연동**: `purpose.py::infer_purpose()`, `necessity.py::classify_necessity()`,
  `action.py::decide_action()`을 `pipeline.py::_assign_default_masked()`가 가져다 써서, 새로 생긴
  `Entity.default_masked`(체크박스 기본값) 필드를 계산한다. ADDRESS/ORGANIZATION만 목적 필요성 판단의
  영향을 받고, 나머지 타입(PERSON/PHONE 등)은 항상 `default_masked=True`. **`purpose_flow.py` 자체
  (전체 오케스트레이터, STEP1-5 한 번에 처리)는 여전히 미연동.**
- **PERSON 마스킹 강화**: `_generic_mask()`(앞 2글자 노출) 대신 `mask_person()`(첫 글자만 노출, 예:
  "홍길동" → `홍**`)을 `pipeline.py`와 `apply_policy.py` 양쪽에 **동일한 코드로 중복 구현**해서 씀.
  현재는 두 구현이 일치하지만, 한쪽만 고치면 어긋날 수 있는 구조라 CLAUDE.md도 이 리스크를 명시해둠.
- **ADDRESS/ORGANIZATION 치환 개선**: 고정 라벨(`[주소]`/`[기관]`) 대신 `replace_address()`/
  `replace_organization()`으로 일반화된 표현 생성 (예: "성신여자대학교 정보보호학과" → "OO대학교 OO학과").

### 5-2. `exaone_client.py::add_position()` 크래시 버그 — 이번 세션에서 수정 완료

이전 턴에서 사용자가 보고한 버그(모델이 `{"text": "..."}` 대신 문자열만 반환하면 `add_position()`이
`AttributeError`로 크래시, 약 1/3 빈도로 재현, `/analyze` 500 에러 원인)를 `backend/app/exaone_client.py`
에서 직접 고쳤다 (dict/str 모두 처리, 리스트가 아닌 값·dict가 아닌 top-level도 방어). 이번 pull로
확인해보니 **CLAUDE.md에도 같은 버그가 이미 "알려진 버그"/"§8 미확정"으로 문서화돼 있었고**,
`pipeline.py` 쪽에는 이미 `try/except`로 감싸 크래시 시 "이번엔 LLM 탐지 없음"으로 넘어가는 임시방편이
있었다 (원인은 자기 파일이 아니라던 주석 포함). 두 수정은 충돌하지 않고, 오히려 이번 수정으로
`try/except`가 발동할 필요 자체가 줄어들어 LLM 탐지가 더 안정적으로 성공하게 된다.
새 테스트: `backend/tests/test_exaone_client.py` (6개, 모두 통과).

### 5-3. `"직접 수정(custom rewrite)"` 기능이 백엔드에 연결 안 되던 문제 — 수정 완료

`extension/ui/result_panel.js`에 이번 pull로 항목별 "직접 수정" 기능이 추가됐다 (협상 카드에서 AI
제안 대신 사용자가 직접 대체 텍스트를 입력하는 UI). 그런데 실제로 값이 백엔드까지 전달되지 않고
있었다 — 사용자에게 "다 고쳐" 확인을 받고 아래처럼 고쳤다.

**증상이었던 것**:
- `result_panel.js`는 `buildDecisions(entities, choices, state.customEntityValues)`처럼 3번째 인자로
  커스텀 텍스트 맵을 넘겼지만, `approval_sender.js::buildDecisions(entities, userChoices)`는 파라미터가
  2개뿐이라 조용히 무시하고 있었음.
- 백엔드 `RewriteRequest`에도 커스텀 텍스트를 실을 필드가 아예 없었음.
- 결과: UI엔 "직접 수정 적용"이라고 표시되지만 실제 `/rewrite`엔 반영 안 되는 조용한 데이터 유실.

**고친 내용**:
1. `backend/app/schemas.py::RewriteRequest`에 `custom_values: dict[str, str] = {}` 필드 추가
   (key: `"TYPE:start:end"`, value: 사용자가 입력한 대체 텍스트).
2. `backend/app/main.py`의 `/rewrite` 핸들러가 `req.custom_values`를 `run_rewrite()`에 전달하도록 수정.
3. `backend/app/pipeline.py::run_rewrite()`가 `custom_values` 파라미터(선택, 하위호환 유지)를 받아
   `_apply_replacements()`에 전달. `_apply_replacements()`는 항목별로 `custom_values`에 값이 있으면
   그걸 쓰고, 없으면 기존처럼 POLICY 기반 치환을 쓴다 — **단 Tier1(고유식별정보)은 custom_values를
   무시하고 항상 강제 마스킹**해서 §5 불변조건(클라이언트/사용자 입력만으로 고유식별정보를 우회 못 함)을
   지킨다. 새 테스트: `backend/tests/test_pipeline_custom_values.py` (3개 — 정상 케이스, Tier1 무시
   케이스, 커스텀 값 없는 기존 호출 하위호환 케이스, 모두 통과). `test_pipeline.py`는 건드리지 않음.
4. `extension/approval_sender.js`에 `buildCustomValues(entities, customEntityValues)` 함수를 새로 추가
   (Tier1은 애초에 안 실어 보내도록 방어)하고, `requestRewrite()`가 4번째 인자로 이 값을 받아
   `REQUEST_REWRITE` 메시지에 실어 보내도록 수정.
5. `extension/background.js::handleRequestRewrite()`가 `payload.customValues`를 `/rewrite` 요청 바디의
   `custom_values` 필드로 전달하도록 수정.
6. `extension/ui/result_panel.js`의 `performQuickRewrite()`/`goRewrite()` 핸들러가
   `ApprovalSender.buildCustomValues()`로 만든 값을 `requestRewrite()`에 실어 보내도록 수정.
7. **죽은 코드 제거**: `state.customRewriteText`(레거시, 이미 "더 이상 사용 안 함"이라고 주석 달려있던
   변수)와 이를 참조하며 존재하지 않는 백엔드 필드(`custom_text`)를 향해 별도 `fetch()`를 날리던
   `goRewrite()`의 도달 불가 분기를 통째로 제거 — 이제 "직접 수정"은 오직 `customEntityValues` →
   `custom_values` 경로 하나로만 흐른다.

검증: 새 pytest 3개 + 기존 `test_exaone_client.py` 6개 모두 통과, `pipeline.py`/`schemas.py`/`main.py`
`py_compile` 통과, 수정한 JS 3개 파일(`result_panel.js`, `approval_sender.js`, `background.js`) 모두
`node --check` 통과. `test_pipeline.py`는 시그니처를 하위호환되게(3번째 인자에 기본값 `None`) 만들어서
따로 손대지 않았다.
