from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    prompt: str


class Entity(BaseModel):
    type: str
    value: str
    start: int
    end: int


class AnalyzeResponse(BaseModel):
    original: str
    masked: str
    entities: list[Entity]
    candidates: list[str]