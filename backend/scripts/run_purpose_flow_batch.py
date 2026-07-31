"""여러 프롬프트를 한 번에 STEP1-5 목적 보존 재작성(app.rewrite.purpose_flow)에
돌려보는 수동 실험용 스크립트. 실제 로컬 Ollama(exaone3.5:2.4b)를 호출하므로
프롬프트 수에 비례해 시간이 걸린다.

사용법 (backend/ 디렉터리에서 실행):
    python scripts/run_purpose_flow_batch.py <입력파일> <출력파일>

입력파일: 한 줄에 프롬프트 하나씩 (빈 줄은 건너뜀).
출력파일: UTF-8로 저장된다 — Windows 콘솔은 한글이 깨질 수 있어 파일로 받고
          에디터로 열어서 보는 걸 권장한다 (§5.2 — 원본/PII를 콘솔에 남기지 않기 위함이기도 함).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rewrite.purpose_flow import rewrite_with_purpose  # noqa: E402


def main() -> None:
    if len(sys.argv) != 3:
        print("사용법: python scripts/run_purpose_flow_batch.py <입력파일> <출력파일>")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    prompts = [
        line.strip()
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    total = len(prompts)

    with output_path.open("w", encoding="utf-8") as out:
        for i, prompt in enumerate(prompts, start=1):
            result = rewrite_with_purpose(prompt)

            out.write(f"=== {i}/{total} ===\n")
            out.write(f"INPUT   : {prompt}\n")
            out.write(f"PURPOSE : {result.purpose}\n")
            for d in result.decisions:
                out.write(
                    f"  [{d.type}] {d.value!r} -> necessary={d.necessary}, action={d.action}\n"
                )
            out.write(f"OUTPUT  : {result.rewritten}\n\n")

            # 진행 상황만 콘솔에 남긴다 — 프롬프트 내용 자체는 출력하지 않는다 (§5.2).
            print(f"[{i}/{total}] 완료")

    print(f"\n전체 {total}건 완료 -> {output_path}")


if __name__ == "__main__":
    main()
