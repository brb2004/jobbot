from app.core.words_core import has_any
from app.services.title_rules_services import PRESALES_TITLES


def test_customer_success_is_a_sales_role():
    assert has_any("Customer Success Engineer", PRESALES_TITLES, hyphen_joins=True)
    assert not has_any("Backend Engineer", PRESALES_TITLES, hyphen_joins=True)
