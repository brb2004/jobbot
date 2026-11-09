from app.services.preferences_services import PRESALES_TITLES, has_any


def test_customer_success_is_a_sales_role():
    assert has_any("Customer Success Engineer", PRESALES_TITLES, hyphen_joins=True)
    assert not has_any("Backend Engineer", PRESALES_TITLES, hyphen_joins=True)
