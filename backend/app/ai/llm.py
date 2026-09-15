from abc import ABC, abstractmethod
import httpx
from app.core.config import settings


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, findings: dict) -> dict: ...


class MockLLMProvider(LLMProvider):
    def generate(self, findings):
        failed = [r for r in findings['rules'] if r['status'] == 'FAIL']
        risk = findings['risk']
        clean = not failed and not risk['contributing_factors']
        blacklist = any(s['type'] == 'blacklisting_hit' for s in risk['contributing_factors'])
        action = 'RECOMMEND NON-COMPLIANT' if blacklist else 'RECOMMEND COMPLIANT' if clean else 'MANUAL REVIEW REQUIRED'
        summary = (f"{findings['bidder_name']} scored {findings['score']['score']}/100 with {risk['risk_level'].lower()} risk. "
                   f"{len(findings['rules'])-len(failed)} of {len(findings['rules'])} tender rules passed. "
                   + ('All configured checks passed against fictional demo sources. ' if clean else
                      'The evidence requires officer attention: ' + '; '.join(r['explanation'] for r in failed) + '. ')
                   + 'This is advisory decision support. The procurement officer retains final authority.')
        confidence = min([v['confidence'] for v in findings['verifications']] or [0])
        return {'provider': 'MockLLMProvider · evidence-based template', 'summary': summary,
                'recommended_action': action, 'confidence': confidence,
                'confidence_explanation': 'Minimum source-check confidence; unavailable or unsubstantiated checks reduce it to zero.',
                'why': [r['explanation'] for r in failed] or ['All enabled tender rules passed'],
                'evidence': [{'rule_result_id': r['result_id'], 'rule_code': r['rule_code'], 'rule': r['name'],
                              'status': r['status'], 'details': r['evidence']} for r in findings['rules']],
                'officer_action': 'Inspect flagged evidence, request clarification as needed, and record an explicit decision with a reason.',
                'reasoning_sources': findings['retrieval'], 'advisory_only': True, 'is_mock': True}


class OptionalOpenAIProvider(LLMProvider):
    """External model may suggest cited phrasing; deterministic findings remain authoritative."""
    def generate(self, findings):
        import json
        result = MockLLMProvider().generate(findings)
        try:
            # Send structured fictional findings only; never document binaries or secrets.
            with httpx.Client(timeout=15) as client:
                response = client.post(settings.llm_base_url.rstrip('/')+'/chat/completions',
                    headers={'Authorization': f'Bearer {settings.llm_api_key}'},
                    json={'model': settings.llm_model, 'temperature': 0,
                          'messages': [{'role': 'system', 'content': 'Return JSON with cited_rule_ids only: choose IDs of failed tender rules requiring review. Do not create facts or recommendations.'},
                                       {'role': 'user', 'content': json.dumps(result['evidence'])}],
                          'response_format': {'type': 'json_object'}})
                response.raise_for_status()
                content = json.loads(response.json()['choices'][0]['message']['content'])
                allowed = {r['rule_result_id'] for r in result['evidence'] if r['status'] == 'FAIL'}
                cited = content.get('cited_rule_ids', [])
                if not isinstance(cited, list) or not set(cited).issubset(allowed):
                    raise ValueError('Ungrounded model citations')
                result['external_cited_rule_ids'] = cited
                result['provider'] = 'OptionalOpenAIProvider (validated citations) + evidence-based summary'
        except Exception:
            result['fallback_reason'] = 'External model unavailable or output ungrounded; evidence-based explanation used'
        return result
