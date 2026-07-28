import re


def replace_organization(value: str) -> str:
    """
    기관명을 유형을 유지한 채 일반화된 표현으로 치환한다.

    예:
    성신여자대학교 정보보호학과 -> OO대학교 OO학과
    ABC 주식회사              -> OO회사
    서울시청                  -> OO기관
    """

    university_match = re.search(r".*?대학교", value)
    department_match = re.search(r"[^\s]*(학과|학부)", value)

    if university_match:

        parts = ["OO대학교"]

        if department_match:
            parts.append("OO학과")

        return " ".join(parts)

    if any(keyword in value for keyword in ("회사", "㈜")) or value.endswith("(주)"):
        return "OO회사"

    return "OO기관"