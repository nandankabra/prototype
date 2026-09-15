from .base import HTTPMockAdapter


class MockOEMAdapter(HTTPMockAdapter):
    source = 'OEM'
    path = 'oem'
