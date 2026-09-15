from .base import HTTPMockAdapter


class MockGSTAdapter(HTTPMockAdapter):
    source = 'GST'
    path = 'gst'
