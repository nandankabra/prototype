from .base import HTTPMockAdapter


class MockPANAdapter(HTTPMockAdapter):
    source = 'PAN'
    path = 'pan'
