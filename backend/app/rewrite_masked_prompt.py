"""하위 호환용 재노출.

이전에는 이 파일 하나에 person/phone/email/label 정리 로직과 LLM 다듬기가 전부
섞여 있었다. 지금은 app/rewrite/ 패키지로 타입별 모듈이 나뉘었고
(person.py, contact_label.py, org_address_label.py, label_strip.py,
llm_polish.py, orchestrator.py), 이 파일은 app.actions.apply_policy 등
기존 코드의 `from app.rewrite_masked_prompt import rewrite_masked_prompt`
임포트가 계속 동작하도록 재노출만 한다.
"""

from app.rewrite.orchestrator import rewrite_masked_prompt

__all__ = ["rewrite_masked_prompt"]
