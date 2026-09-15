from .base import HTTPMockAdapter


class MockBlacklistingAdapter(HTTPMockAdapter):
    source = 'BLACKLIST'
    path = 'blacklist'
