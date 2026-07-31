from app.rewrite.action import decide_action


def test_person_is_always_generalized_regardless_of_necessity():
    assert decide_action("PERSON", necessary=True) == "generalize"
    assert decide_action("PERSON", necessary=False) == "generalize"


def test_contact_types_are_always_deleted_regardless_of_necessity():
    for entity_type in ("PHONE", "EMAIL", "BANK_ACCOUNT", "STUDENT_ID"):
        assert decide_action(entity_type, necessary=True) == "delete"
        assert decide_action(entity_type, necessary=False) == "delete"


def test_tier1_types_are_always_deleted():
    for entity_type in ("RRN", "PASSPORT", "DRIVER_LICENSE", "FOREIGNER_REGISTRATION"):
        assert decide_action(entity_type, necessary=True) == "delete"


def test_organization_and_address_judge_by_necessity():
    assert decide_action("ORGANIZATION", necessary=True) == "keep"
    assert decide_action("ORGANIZATION", necessary=False) == "delete"
    assert decide_action("ADDRESS", necessary=True) == "keep"
    assert decide_action("ADDRESS", necessary=False) == "delete"


def test_unknown_type_falls_back_to_necessity():
    assert decide_action("UNKNOWN_TYPE", necessary=True) == "keep"
    assert decide_action("UNKNOWN_TYPE", necessary=False) == "delete"
