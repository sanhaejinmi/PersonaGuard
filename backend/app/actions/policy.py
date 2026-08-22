POLICY = {

    # ==========================
    # Regex 기반
    # ==========================

    "RRN": "mask",
    "PHONE": "mask",
    "DRIVER_LICENSE": "mask",
    "BANK_ACCOUNT": "mask",
    "CARD": "mask",
    "PASSPORT": "mask",
    "FOREIGNER_REGISTRATION": "mask",

    "EMAIL": "replace",
    "BUSINESS_NUMBER": "mask",

    # ==========================
    # LLM 기반
    # ==========================

    "PERSON": "mask",
    "ADDRESS": "replace",
    "ORGANIZATION": "replace",
}