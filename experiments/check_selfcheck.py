"""2-B 재작성 결과에 self_check가 무엇을 걸고 있는지 센다.

기본은 정규식 + 잔여라벨만 확인해서 즉시 끝난다 (Ollama 안 씀 — test 실행 중에도 안전).
--llm 을 주면 detect_llm까지 돌린다 (문항당 LLM 1회, 느림).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from app.regex_engine import detect_regex
from app.rewrite.self_check import _RESIDUAL_LABEL_PATTERN


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", default="experiments/out/exp2b/per_case.jsonl")
    ap.add_argument("--llm", action="store_true")
    args = ap.parse_args()

    detect_llm = None
    if args.llm:
        from app.exaone_client import detect_llm

    n = 0
    flagged_regex = 0
    flagged_any = 0
    types: Counter = Counter()

    for line in Path(args.jsonl).open(encoding="utf-8"):
        r = json.loads(line)
        text = r["output_text"]
        n += 1
        hits: Counter = Counter()

        for e in detect_regex(text):
            hits[e["type"]] += 1
        residual = sum(1 for _ in _RESIDUAL_LABEL_PATTERN.finditer(text))
        if residual:
            hits["RESIDUAL_LABEL"] += residual

        if hits:
            flagged_regex += 1

        if detect_llm is not None:
            try:
                for t, items in (detect_llm(text) or {}).items():
                    if items:
                        hits[f"LLM_{t}"] += len(items)
            except Exception:
                pass

        if hits:
            flagged_any += 1
            types.update(hits.keys())

    print(f"총 {n}건")
    print(f"  정규식·잔여라벨만으로 flag: {flagged_regex} ({flagged_regex/n:.1%})")
    if detect_llm is not None:
        print(f"  LLM 포함 flag:            {flagged_any} ({flagged_any/n:.1%})")
    print("  flag를 유발한 항목 (건수 기준):")
    for t, c in types.most_common():
        print(f"    {t:24s} {c:4d}건")


if __name__ == "__main__":
    main()