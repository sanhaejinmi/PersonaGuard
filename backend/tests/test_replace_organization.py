from app.replace.replace_organization import replace_organization


def test_university_and_department_generalized():
    assert replace_organization("성신여자대학교 정보보호학과") == "OO대학교 OO학과"


def test_university_only_generalized():
    assert replace_organization("성신여자대학교") == "OO대학교"


def test_major_alone_generalized_as_major_not_generic_org():
    assert replace_organization("경영전공") == "OO전공"


def test_department_alone_generalized_as_department_not_generic_org():
    assert replace_organization("경영학과") == "OO학과"


def test_university_with_major_generalized():
    assert replace_organization("성신여자대학교 경영전공") == "OO대학교 OO전공"


def test_company_generalized():
    assert replace_organization("ABC 주식회사") == "OO회사"


def test_generic_organization_fallback():
    assert replace_organization("서울시청") == "OO기관"
