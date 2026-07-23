"""
Session Store — 세션별 원본 프롬프트·탐지 항목(tier 포함) 매핑 보관 (In-Memory).

§5.6 불변조건: 요청 간 격리 보장. session_id는 pipeline.run_analysis() 호출마다
새로 발급되고, session_id를 모르면 다른 세션 데이터에 접근할 수 없다.

TTL·용량 정책은 §8 미확정 — 팀 확인 후 만료 처리를 추가할 것.
"""

import threading
from typing import Any

_store: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def create(session_id: str, original: str, items: list[dict]) -> None:
    with _lock:
        _store[session_id] = {"original": original, "items": items}


def get(session_id: str) -> dict[str, Any] | None:
    with _lock:
        return _store.get(session_id)


def delete(session_id: str) -> None:
    with _lock:
        _store.pop(session_id, None)
