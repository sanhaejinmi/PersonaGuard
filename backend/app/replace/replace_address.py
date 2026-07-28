import re


def replace_address(address: str) -> str:
    """
    주소를 시/도 + 시/군/구까지만 남긴다.

    예)
    서울특별시 금천구 시흥5동 가길 49
    → 서울특별시 금천구

    경기도 성남시 분당구 정자동 15
    → 경기도 성남시 분당구

    부산광역시 해운대구 우동 123
    → 부산광역시 해운대구
    """

    parts = address.split()

    if len(parts) < 2:
        return address

    # 첫 번째가 시/도
    province = parts[0]

    # 서울특별시 금천구
    if province.endswith(("특별시", "광역시", "특별자치시")):

        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"

    # 경기도 성남시 분당구
    elif province.endswith(("도", "특별자치도")):

        if len(parts) >= 3:
            return f"{parts[0]} {parts[1]} {parts[2]}"

    return " ".join(parts[:2])