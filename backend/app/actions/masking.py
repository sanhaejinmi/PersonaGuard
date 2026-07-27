import re


def _generic_mask(value: str) -> str:
    """
    형식이 예상과 다를 때 사용하는 보수적 마스킹
    앞 2자리만 남기고 나머지는 전부 마스킹
    """
    if len(value) <= 2:
        return "*" * len(value)

    return value[:2] + "*" * (len(value) - 2)


def mask_value(value, entity_type):

    if entity_type == "RRN":

        match = re.match(r"(\d{6})-(\d)(\d{6})", value)

        if match:
            return f"{match.group(1)}-{match.group(2)}******"

        return _generic_mask(value)

    elif entity_type == "PHONE":

        match = re.match(r"(\d{3})-(\d{4})-(\d{4})", value)

        if match:
            return (
                f"{match.group(1)}-"
                f"{match.group(2)[:2]}**-"
                f"****"
            )

        return _generic_mask(value)

    elif entity_type == "DRIVER_LICENSE":

        match = re.match(r"(\d{2})-(\d{2})-(\d{6})-(\d{2})", value)

        if match:
            return (
                f"{match.group(1)}-"
                f"{match.group(2)}-"
                f"XXXXXX-XX"
            )

        return _generic_mask(value)

    elif entity_type == "BANK_ACCOUNT":

        parts = value.split("-")

        if len(parts) == 3:
            return parts[0] + "-" + "**" + "-" + "******"

        return _generic_mask(value)

    elif entity_type == "CARD":

        parts = value.split("-")

        if len(parts) == 4:
            return parts[0] + "-" + "XXXX" + "-" + "XXXX" + "-" + parts[3]

        return _generic_mask(value)

    elif entity_type == "BUSINESS_NUMBER":

        match = re.match(r"(\d{3})-(\d{2})-(\d{5})", value)

        if match:
            return f"{match.group(1)}-{match.group(2)}-XXXXX"

        return _generic_mask(value)

    elif entity_type == "PASSPORT":

        return "*" * len(value)

    elif entity_type == "FOREIGNER_REGISTRATION":

        match = re.match(r"(\d{6})-(\d)(\d{6})", value)

        if match:
            return f"{match.group(1)}-{match.group(2)}******"

        return _generic_mask(value)

    return _generic_mask(value)