from .base import HTTPMockAdapter


class MockNSICAdapter(HTTPMockAdapter):
    source = 'NSIC'
    path = 'nsic'
