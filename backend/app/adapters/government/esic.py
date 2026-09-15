from .base import HTTPMockAdapter


class MockESICAdapter(HTTPMockAdapter):
    source = 'ESIC'
    path = 'esic'
