"""
PersonaGuard 실험 코드 — "PersonaGuard 실험 계획" 문서(실험 1·2·3)를 실행하는 하네스.

이 패키지는 app/ 아래 실서비스 코드를 전혀 수정하지 않는다. app.pipeline의
run_analysis()/run_rewrite()를 읽기 전용으로 호출만 하고, 마스킹/치환 빌딩
블록(app.actions.*, app.replace.*)도 그대로 재사용한다.

이 패키지는 PersonaGuard 레포 루트(backend/와 형제)에 있지만, app 패키지는
backend/app에 있다 — 그래서 import app.* 가 되도록 backend/를 sys.path에
등록해둔다. 실행 위치(cwd)와 무관하게 항상 동작하도록, 이 파일이 처음
로드될 때(즉 experiments 하위 모듈이 처음 import될 때) 한 번만 등록한다.
"""

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
