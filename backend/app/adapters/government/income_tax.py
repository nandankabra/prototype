from .base import HTTPMockAdapter


class MockIncomeTaxAdapter(HTTPMockAdapter):
    source = 'INCOME_TAX'
    path = 'itr'
