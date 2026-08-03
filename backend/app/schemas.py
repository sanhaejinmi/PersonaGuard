from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    prompt: str


class Entity(BaseModel):
    type: str
    value: str
    start: int
    end: int
    tier: int  # 1=고유식별정보(강제마스킹) 2=연락·계정정보 3=생활문맥정보(EEVE) — CLAUDE.md §3.1
    default_masked: bool  # AI가 제안하는 체크박스 기본값. Tier1은 항상 True.


class AnalyzeResponse(BaseModel):
    session_id: str
    original: str
    masked: str
    entities: list[Entity]
    candidates: list[str]  # entities와 동일 index로 매칭되는 치환 미리보기 (Extension 협상 화면용)


class RewriteRequest(BaseModel):
    session_id: str
    decisions: dict[str, bool]  # key: "TYPE:start:end", value: 보호(True)/원문유지(False)


class RewriteResponse(BaseModel):
    rewritten: str