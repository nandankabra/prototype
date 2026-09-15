from .base import HTTPMockAdapter


class MockDigiLockerAdapter(HTTPMockAdapter):
    source = 'DIGILOCKER'
    path = 'digilocker'
