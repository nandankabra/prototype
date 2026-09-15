from .base import HTTPMockAdapter


class MockUdyamAdapter(HTTPMockAdapter):
    source = 'UDYAM'
    path = 'udyam'
