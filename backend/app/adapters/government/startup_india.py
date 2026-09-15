from .base import HTTPMockAdapter


class MockStartupIndiaAdapter(HTTPMockAdapter):
    source = 'STARTUP_INDIA'
    path = 'startup'
