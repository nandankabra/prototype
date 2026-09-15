DEFAULT_WEIGHTS = {'Document completeness': 20, 'Government verification': 30,
                   'Tender eligibility': 25, 'Document validity': 10,
                   'Identity consistency': 10, 'Anomaly signals': 5}


def calculate_score(*, required, documents, verifications, rules, expired_ids, identity_checks, signals, weights):
    """Each earned contribution is a weighted fraction of observable checks."""
    present = {d.classification for d in documents if d.raw_text.strip()}
    identity_passed = sum(check['status'] == 'MATCH' for check in identity_checks)
    validity_total = max(len(documents), 1)
    parts = [
        ('Document completeness', sum(kind in present for kind in required), len(required),
         [f"{kind}: {'present' if kind in present else 'missing'}" for kind in required]),
        ('Government verification', sum(v.status == 'VERIFIED' for v in verifications), len(verifications),
         [f'{v.source}: {v.status}' for v in verifications]),
        ('Tender eligibility', sum(r['status'] == 'PASS' for r in rules), len(rules),
         [f"{r['rule_code']}: {r['status']} — {r['name']}" for r in rules]),
        ('Document validity', max(0, len(documents)-len(expired_ids)), validity_total,
         [f'{len(expired_ids)} documents expired or with unknown required validity out of {len(documents)}']),
        ('Identity consistency', identity_passed, len(identity_checks),
         [f"{c['label']}: {c['status']}" for c in identity_checks]),
        ('Anomaly signals', max(0, 5-len(signals)), 5,
         [f"{s['type']}: {s['description']}" for s in signals] or ['No rule-based risk signals'])]
    breakdown = []
    for name, passed, total, evidence in parts:
        maximum = weights.get(name, 0)
        earned = round(maximum * passed / total, 2) if total else 0
        breakdown.append({'component': name, 'weight': maximum, 'earned': earned, 'lost': round(maximum-earned, 2),
                          'passed': passed, 'total': total, 'evidence': evidence})
    return {'score': round(sum(p['earned'] for p in breakdown), 1), 'maximum': sum(weights.values()),
            'breakdown': breakdown, 'method': 'Sum of configured component weight × observed pass fraction. Unknown checks earn no credit.'}
