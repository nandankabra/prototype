from .base import HTTPMockAdapter


class MockEPFOAdapter(HTTPMockAdapter):
    source = 'EPFO'
    path = 'epfo'
