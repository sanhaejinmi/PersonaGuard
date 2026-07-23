from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import pipeline
from app.schemas import AnalyzeRequest, AnalyzeResponse, RewriteRequest, RewriteResponse
from app.config import settings

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

    try:
        return pipeline.run_analysis(req.prompt)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post(
    "/rewrite",
    response_model=RewriteResponse,
    summary="Rewrite prompt",
    description="Apply the user's confirmed masking decisions and return the purpose-preserving rewritten prompt."
)
def rewrite(req: RewriteRequest):

    if not req.session_id.strip():
        raise HTTPException(
            status_code=400,
            detail="session_id must not be empty."
        )

    try:
        rewritten = pipeline.run_rewrite(req.session_id, req.decisions)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    return RewriteResponse(rewritten=rewritten)