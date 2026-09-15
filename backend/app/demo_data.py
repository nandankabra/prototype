import uuid

NAMES = ['Zenith Industrial Systems Pvt. Ltd.', 'ABC Industrial Solutions Pvt. Ltd.',
         'Meridian Safety Products Pvt. Ltd.', 'Coral Engineering Works Pvt. Ltd.',
         'Atlas Protective Systems Pvt. Ltd.', 'Crestline Industrial Supply Pvt. Ltd.',
         'ABC Industrial Solutions Pvt Ltd', 'Harbor Technical Services Pvt. Ltd.',
         'Aster Process Controls Pvt. Ltd.', 'Summit Mechanical Works Pvt. Ltd.',
         'Vertex Energy Systems Pvt. Ltd.', 'Orion Safety Technologies Pvt. Ltd.',
         'Pioneer Industrial Equipment Pvt. Ltd.', 'Trident Maintenance Services Pvt. Ltd.',
         'Nova Instrumentation Pvt. Ltd.']
SCENARIOS = ['MULTI_RISK', 'GST_MISMATCH', 'CLEAN', 'EXPIRED_DOCUMENT', 'MISSING_OEM', 'BLACKLIST',
             'NAME_VARIATION', 'CLEAN', 'CLEAN', 'EXPIRED_DOCUMENT', 'CLEAN', 'MISSING_OEM', 'CLEAN', 'CLEAN', 'GST_MISMATCH']
TENDER_TITLES = ['Supply of Industrial Safety Equipment', 'Refinery Instrumentation & Control Systems',
                 'Mechanical Maintenance Services', 'Supply of Electrical Protection Equipment', 'Environmental Monitoring Systems']


def stable_id(name):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, 'bytecode-verify.demo.'+name))


def bidder_record(index):
    pan = f'ABCD{chr(65+index)}{1000+index}F'
    gst = '33'+pan+'1Z5'
    name = NAMES[index].replace('Pvt. Ltd.', 'Private Limited').replace('Pvt Ltd', 'Private Limited')
    identifier = stable_id(f'bidder-{index}')
    # Two distinct bids for ABC use the same fictional registered identity.
    if index == 6:
        pan, gst = 'ABCDB1001F', '33ABCDB1001F1Z5'
    base = {'company_name': name, 'status': 'ACTIVE', 'is_fictional': True}
    sources = {key: {**base, 'identifier': value} for key, value in {
        'PAN': pan, 'GST': gst, 'UDYAM': f'UDYAM-TN-02-{1000000+index}', 'INCOME_TAX': pan,
        'EPFO': f'TNDEMO{100000+index}', 'ESIC': f'ESIC-DEMO-{index:04}', 'STARTUP_INDIA': f'DPIIT-DEMO-{index:04}',
        'NSIC': f'NSIC-DEMO-{index:04}', 'DIGILOCKER': f'DL-DEMO-{index:04}', 'BLACKLIST': pan,
        'OEM': f'OEM-DEMO-{index:04}'}.items()}
    sources['BLACKLIST'].update(listed=index == 5, status='LISTED' if index == 5 else 'CLEAR')
    sources['INCOME_TAX']['status'] = 'FILED'
    sources['OEM'].update(status='VALID', valid_until='2028-12-31')
    return identifier, sources
