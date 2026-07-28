from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    RewriteRequest,
    RewriteResponse,
)
from app.config import settings
from app.pipeline import run_analysis, run_rewrite

app = FastAPI(
    title="PersonaGuard API",
    description="Prompt Negotiation Security Agent Backend",
    version="0.1.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 개발 단계에서는 모두 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "message": "PersonaGuard Backend is running!",
        "model": settings.MODEL_NAME
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


# 현재는 임시 서비스 함수
# 나중에 내부를 pipeline.py 호출로 변경하면 됨
def analyze_service(prompt: str) -> AnalyzeResponse:
    return run_analysis(prompt)


@app.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze prompt",
    description="Analyze the user's prompt, detect sensitive information, and return a masked prompt."
)
def analyze(req: AnalyzeRequest):

    # 빈 문자열 예외 처리
    if not req.prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="Prompt must not be empty."
        )

    return analyze_service(req.prompt)

@app.post(
    "/rewrite",
    response_model=RewriteResponse,
    summary="Rewrite prompt",
    description="Apply the user's masking decisions and return the rewritten prompt."
)
def rewrite(req: RewriteRequest):

    try:
        from app.pipeline import run_rewrite

        rewritten = run_rewrite(
            req.session_id,
            req.decisions
        )

        return RewriteResponse(
            rewritten=rewritten
        )

    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Session not found."
        )  