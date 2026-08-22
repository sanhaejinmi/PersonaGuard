# PersonaGuard

**생성형 AI 프롬프트의 개인정보 보호와 목적 보존을 위한 협상형 보안 에이전트**

팀 자양강장이 | 2026 융합보안소프트웨어 경진대회

---

ChatGPT·Claude 같은 생성형 AI에 프롬프트를 전송하기 **직전**에 개입해, 프롬프트에 포함된
개인정보를 탐지하고 사용자와 항목 단위로 협상한 뒤, 질문의 목적을 보존한 형태로 재작성합니다.

모든 처리는 로컬에서 이루어지며, 사용자가 승인하기 전까지 원문은 외부로 전송되지 않습니다.

**구조**: Chrome 확장(MV3) → FastAPI(127.0.0.1:8000) → Ollama / EXAONE 3.5

| 구성 | 역할 |
|---|---|
| `extension/` | 입력 가로채기, 협상 UI |
| `backend/` | 탐지·정책 판단·재작성 파이프라인 |
| `experiments/` | 성능 평가 실험 코드 및 결과 |
| `docs/` | 설계 문서 |

---

## 실행 방법

브라우저 확장만 로드하면 동작하지 않습니다. **Ollama → 백엔드 → 확장** 순서로 실행해야 합니다.

### 1. Ollama 및 모델 준비

[ollama.com](https://ollama.com)에서 Ollama를 설치한 뒤 모델 두 개를 받습니다.

```bash
ollama pull exaone3.5:2.4b
ollama pull exaone3.5:7.8b
```

`2.4b`는 탐지, `7.8b`는 필요성 판단과 재작성에 사용되므로 **두 개 모두 필요합니다.**

```bash
ollama list        # 두 모델이 보이면 준비 완료
```

### 2. 백엔드 실행

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --port 8000
```

`Uvicorn running on http://127.0.0.1:8000` 이 출력되면 정상입니다.
**이 터미널 창은 닫지 마십시오.** 확장이 이 서버를 호출합니다.

동작 확인 (다른 터미널에서):

```bash
curl http://127.0.0.1:8000/
# {"message":"PersonaGuard Backend is running!","model":"EXAONE"}
```

### 3. 확장 로드

1. Chrome 주소창에 `chrome://extensions`
2. 우측 상단 **개발자 모드** 켜기
3. **압축해제된 확장 프로그램을 로드합니다** 클릭
4. 이 저장소의 `extension` 폴더 선택

---

## 사용

`chatgpt.com` 또는 `claude.ai`에서 입력창에 프롬프트를 입력하고 **Enter** 를 누릅니다.

예시 입력:

```
안녕하세요, 김민준입니다. 주민등록번호는 900101-1234567이고
연락처는 010-1234-5678입니다. 대출 상담 받고 싶어요.
```

1. 전송이 보류되고 개인정보 분석이 시작됩니다
2. 탐지된 항목이 위험도(Tier)와 함께 표시됩니다
3. 항목별로 마스킹 여부를 선택합니다

   | 등급 | 대상 | 처리 |
   |---|---|---|
   | **Tier 1** | 주민등록번호·여권번호·운전면허번호·외국인등록번호 | 선택과 무관하게 **강제 마스킹** |
   | **Tier 2** | 전화번호·이메일·계좌·카드·사업자등록번호 | 기본 마스킹, 해제 시 경고 |
   | **Tier 3** | 이름·주소·소속기관 | 질문 목적상 필요성을 판단해 기본값 제안, 사용자가 변경 가능 |

4. 목적을 보존한 형태로 재작성된 프롬프트를 확인합니다
5. 승인하면 재작성된 프롬프트가 전송됩니다

> **응답에 30초~1분이 걸릴 수 있습니다.** 프롬프트 하나당 로컬 LLM을 3~4회 호출하므로 정상입니다.

---

## 문제 해결

### `[PersonaGuard] 분석 요청 실패 TypeError: Failed to fetch`

**백엔드가 실행되고 있지 않습니다.** 가장 흔한 원인입니다. 실행 방법 2번을 다시 확인하십시오.

`chrome://extensions` → PersonaGuard → **서비스 워커** → Network 탭에서
`/analyze` 요청의 Status Code가 `200`인지 확인할 수 있습니다.

### Enter를 눌러도 아무 일이 없음

- 전송 **버튼 클릭이 아니라 Enter 키**로 입력해야 합니다. 확장은 keydown 이벤트만 가로챕니다.
- 지원 사이트는 `chatgpt.com`, `chat.openai.com`, `claude.ai` 입니다.
- 확장 로드 후 페이지를 새로고침했는지 확인하십시오.

### 백엔드가 500 오류를 반환

Ollama가 실행 중이고 모델 두 개가 모두 설치되어 있는지 확인하십시오.

```bash
curl http://localhost:11434/api/tags
```

---

## 실험 재현

실험 코드와 데이터, 실행 결과는 `experiments/` 아래에 있습니다.

```bash
# 실험 2-A — 정답 span 제공, Ollama 불필요 (수 초)
python -m experiments.run_exp2 --mode 2a --splits dev val test challenge --out experiments/out/exp2a

# 실험 2-B — 전체 파이프라인, Ollama 필요 (장시간)
python -m experiments.run_exp2_all --splits dev --decisions default --out experiments/out/exp2b_dev
```

각 결과 폴더의 의미는 `experiments/out/README.md`를 참고하십시오.
