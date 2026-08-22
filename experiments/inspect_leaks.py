"""2-B 누출 항목이 '탐지 실패'인지 'AI가 목적상 필요 판단 → 기본 유지'인지 분류한다.

실행:
    python -m experiments.inspect_leaks --jsonl experiments\\out\\exp2b_test\\per_case.jsonl --splits test
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from app.pipeline import run_analysis

DATA = Path("experiments/data")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", required=True, type=Path)
    ap.add_argument("--splits", nargs="+", required=True)
    args = ap.parse_args()

    prompts = {}
    for split in args.splits:
        with (DATA / f"PersonaGuard_exp2_{split}.csv").open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                prompts[row["id"]] = row["v1_prompt"]

    tally: Counter = Counter()
    for line in args.jsonl.open(encoding="utf-8"):
        r = json.loads(line)
        if not r["leaked"]:
            continue
        resp = run_analysis(prompts[r["case_id"]])
        for leak in r["leaked"]:
            hit = [e for e in resp.entities
                   if leak["text"] in e.value or e.value in leak["text"]]
            if not hit:
                verdict = "탐지실패"
                detail = ""
            else:
                e = hit[0]
                verdict = "기본유지" if not e.default_masked else "기타"
                detail = f"value={e.value!r} tier={e.tier} default_masked={e.default_masked}"
            tally[(leak["type"], verdict)] += 1
            print(f"{r['case_id']:22s} {leak['type']:13s} {leak['text'][:26]:28s} -> {verdict} {detail}")

    print("\n=== 집계 ===")
    for (etype, verdict), n in sorted(tally.items()):
        print(f"  {etype:13s} {verdict:8s} {n:3d}건")
    print(f"  합계 {sum(tally.values())}건")


if __name__ == "__main__":
    main()