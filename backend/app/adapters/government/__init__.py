from .udyam import MockUdyamAdapter
from .gst import MockGSTAdapter
from .pan import MockPANAdapter
from .income_tax import MockIncomeTaxAdapter
from .epfo import MockEPFOAdapter
from .esic import MockESICAdapter
from .startup_india import MockStartupIndiaAdapter
from .nsic import MockNSICAdapter
from .digilocker import MockDigiLockerAdapter
from .blacklist import MockBlacklistingAdapter
from .oem import MockOEMAdapter

ADAPTERS = [MockUdyamAdapter, MockGSTAdapter, MockPANAdapter, MockIncomeTaxAdapter, MockEPFOAdapter, MockESICAdapter, MockStartupIndiaAdapter, MockNSICAdapter, MockDigiLockerAdapter, MockBlacklistingAdapter, MockOEMAdapter]
