"""
실험용 데이터셋 스키마 및 로더.

"PersonaGuard 실험 계획" §1~§5을 그대로 코드로 옮긴다:
- TestCase 1건 = Seed Prompt + V1(가짜 개인정보 삽입) + 정답 라벨(GoldEntity 목록)
- 같은 문제의 변형(family_id)은 절대 dev/val 묶음과 test/challenge 묶음에
  나눠 들어가면 안 된다 (§4 6단계, §12 규칙1) — validate_split_isolation()으로 확인.

여기서 쓰는 entity type은 PersonaGuard가 실제로 탐지하는 타입(정규식 9종 +
LLM PERSON/ADDRESS/ORGANIZATION)으로 한정한다. 나이·성별처럼 시스템이 아직
탐지하지 못하는 항목은 gold_entities에 넣지 않는다 — 넣으면 PersonaGuard가
원리적으로 못 맞히는 실험이 되어 실험 1·2 점수가 왜곡된다.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SPLITS = ("dev", "val", "test", "challenge")

DOMAINS = (
    "health",       # 건강·의료
    "legal_admin",  # 법률·공공행정
    "career_edu",   # 채용·교육·커리어
    "travel_local",  # 여행·지역추천
    "finance_cs",   # 금융·소비자·고객지원
    "coding_tech",  # 코딩·기술지원
)

# §2 Test Set 안에서의 문제 종류 (test/challenge 케이스에만 사용)
TEST_CATEGORIES = (
    "no_pii",         # 개인정보가 아예 없는 문제
    "optional_pii",   # 있어도 되고 없어도 되는 개인정보
    "essential_pii",  # 답에 꼭 필요한 개인정보
    "mixed_pii",      # 필요/불필요 정보가 섞인 문제
)

NECESSITY_LEVELS = ("essential", "optional", "unnecessary")
ACTIONS = ("delete", "mask", "generalize", "keep")

# §9 Challenge Set 함정 종류
CHALLENGE_TRAPS = (
    "obfuscation",              # 띄어쓰기·특수문자로 숨긴 정보
    "split_across_sentences",   # 여러 문장에 나눠서 흘린 정보
    "aggregation",               # 여러 조각을 합치면 알 수 있는 정보
    "embedded_in_code",          # 표·코드·로그 안에 숨은 정보
    "adversarial_instruction",   # "이건 절대 지우지 마세요" 같은 함정 지시
)

# PersonaGuard가 실제로 다루는 entity type (CLAUDE.md §3.1, §4.1/§4.2)
KNOWN_ENTITY_TYPES = (
    "RRN", "PASSPORT", "DRIVER_LICENSE", "FOREIGNER_REGISTRATION",       # Tier1
    "PHONE", "EMAIL", "BANK_ACCOUNT", "CARD", "BUSINESS_NUMBER",          # Tier2
    "PERSON", "ADDRESS", "ORGANIZATION",                                   # Tier3
)


@dataclass
class GoldEntity:
    """§5 정답 라벨 표의 한 항목. start/end는 v1_prompt 기준 유니코드 코드포인트 인덱스 (§4.4)."""

    text: str
    type: str
    start: int
    end: int
    risk: int  # 1(낮음)~5(높음). Tier1급 고유식별정보는 5로 표기 권장.
    necessity: str  # essential / optional / unnecessary
    action: str  # delete / mask / generalize / keep — 사람이 정한 "정답 처리 방법"
    labeler_1: str | None = None
    labeler_2: str | None = None

    def __post_init__(self) -> None:
        if self.necessity not in NECESSITY_LEVELS:
            raise ValueError(f"unknown necessity: {self.necessity!r}")
        if self.action not in ACTIONS:
            raise ValueError(f"unknown action: {self.action!r}")
        if self.type not in KNOWN_ENTITY_TYPES:
            raise ValueError(f"unknown entity type: {self.type!r}")
        if self.start < 0 or self.end <= self.start:
            raise ValueError(f"invalid span [{self.start}, {self.end}) for {self.text!r}")


@dataclass
class TestCase:
    """§1/§5 문제 하나. family_id로 "같은 문제의 변형"을 묶는다."""

    id: str
    split: str
    domain: str
    family_id: str
    purpose: str  # "이 질문이 원하는 것" (§5)
    seed_prompt: str  # 개인정보 넣기 전 원래 질문
    v1_prompt: str  # 가짜 개인정보가 들어간 질문 — 실험 1·2·3의 실제 입력
    gold_entities: list[GoldEntity] = field(default_factory=list)
    test_category: str | None = None  # test/challenge에서만 사용 (§2)
    challenge_trap: str | None = None  # challenge에서만 사용 (§9)
    source_ref: str | None = None  # 참고한 공개 데이터 출처 (§3) — 원문 복사 아님, 출처 표기용

    def __post_init__(self) -> None:
        if self.split not in SPLITS:
            raise ValueError(f"unknown split: {self.split!r}")
        if self.domain not in DOMAINS:
            raise ValueError(f"unknown domain: {self.domain!r}")
        if self.test_category is not None and self.test_category not in TEST_CATEGORIES:
            raise ValueError(f"unknown test_category: {self.test_category!r}")
        if self.challenge_trap is not None and self.challenge_trap not in CHALLENGE_TRAPS:
            raise ValueError(f"unknown challenge_trap: {self.challenge_trap!r}")
        for g in self.gold_entities:
            if self.v1_prompt[g.start : g.end] != g.text:
                raise ValueError(
                    f"[{self.id}] gold entity span mismatch: "
                    f"expected {g.text!r}, got {self.v1_prompt[g.start:g.end]!r} "
                    f"at [{g.start}:{g.end}]"
                )


def _case_from_dict(raw: dict) -> TestCase:
    entities = [GoldEntity(**e) for e in raw.get("gold_entities", [])]
    kwargs = {k: v for k, v in raw.items() if k != "gold_entities"}
    return TestCase(gold_entities=entities, **kwargs)


def _load_csv_dataset(path: Path) -> list[TestCase]:
    """실험 2용 prompt-level CSV를 TestCase 목록으로 변환한다.

    ``gold_entities_json``은 GoldEntity 객체 배열을 담는다. 빈 문자열로 저장된
    선택 필드는 dataclass 검증 전에 ``None``으로 정규화한다.
    """
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {
            "id", "split", "domain", "family_id", "purpose", "seed_prompt",
            "v1_prompt", "gold_entities_json",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"input CSV is missing columns: {sorted(missing)}")

        cases = []
        for row_number, row in enumerate(reader, start=2):
            try:
                entities = json.loads(row["gold_entities_json"] or "[]")
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid gold_entities_json at CSV row {row_number}: {exc}"
                ) from exc
            raw = {
                "id": row["id"],
                "split": row["split"],
                "domain": row["domain"],
                "family_id": row["family_id"],
                "purpose": row["purpose"],
                "seed_prompt": row["seed_prompt"],
                "v1_prompt": row["v1_prompt"],
                "gold_entities": entities,
                "test_category": row.get("test_category") or None,
                "challenge_trap": row.get("challenge_trap") or None,
                "source_ref": row.get("source_ref") or None,
            }
            cases.append(_case_from_dict(raw))
    return cases


def load_dataset(path: str | Path) -> list[TestCase]:
    """JSON 또는 실험 2 prompt-level CSV에서 테스트 케이스를 읽는다.

    최상위가 리스트여도 되고, {"meta": {...}, "cases": [...]} 형태여도 된다.
    """
    dataset_path = Path(path)
    if dataset_path.suffix.lower() == ".csv":
        return _load_csv_dataset(dataset_path)

    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases_raw = raw["cases"] if isinstance(raw, dict) else raw
    return [_case_from_dict(c) for c in cases_raw]


def save_dataset(cases: list[TestCase], path: str | Path, meta: dict | None = None) -> None:
    payload: dict | list
    cases_dicts = [asdict(c) for c in cases]
    payload = {"meta": meta, "cases": cases_dicts} if meta else cases_dicts
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_split_isolation(cases: list[TestCase]) -> list[str]:
    """§4 6단계 / §12 규칙1 — 같은 family_id가 dev/val(연습장·모의고사)과
    test/challenge(진짜시험) 양쪽에 걸쳐 있으면 데이터 유출이다. 위반 목록을 문자열로 반환한다."""
    dev_val_families: dict[str, set[str]] = {}
    test_challenge_families: dict[str, set[str]] = {}
    for c in cases:
        bucket = dev_val_families if c.split in ("dev", "val") else test_challenge_families
        bucket.setdefault(c.family_id, set()).add(c.id)

    warnings = []
    leaked = set(dev_val_families) & set(test_challenge_families)
    for family_id in sorted(leaked):
        dev_ids = sorted(dev_val_families[family_id])
        test_ids = sorted(test_challenge_families[family_id])
        warnings.append(
            f"family_id={family_id!r}가 dev/val({dev_ids})과 test/challenge({test_ids})에 "
            "동시에 존재함 — 같은 문제의 변형이 양쪽에 섞이면 안 됨 (§4 6단계)"
        )
    return warnings


def filter_cases(
    cases: list[TestCase],
    split: str | None = None,
    domain: str | None = None,
    test_category: str | None = None,
) -> list[TestCase]:
    result = cases
    if split is not None:
        result = [c for c in result if c.split == split]
    if domain is not None:
        result = [c for c in result if c.domain == domain]
    if test_category is not None:
        result = [c for c in result if c.test_category == test_category]
    return result
