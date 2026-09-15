import { request } from './api';
import type { Review } from '../types';
export function registerReviewTool() {
  const context = (document as Document & {modelContext?: {registerTool: (tool: unknown, options: {signal: AbortSignal}) => void}}).modelContext;
  if (!context?.registerTool) return;
  const lifecycle = new AbortController();
  try {
    Promise.resolve(context.registerTool({
      name: 'read_bid_compliance_evidence', title: 'Read bid compliance evidence',
      description: 'Read the current saved review and its evidence references. Does not make an officer decision or start processing.',
      inputSchema: {type:'object',properties:{bid_id:{type:'string',format:'uuid'}},required:['bid_id'],additionalProperties:false},
      annotations: {readOnlyHint:true,untrustedContentHint:true},
      async execute(input: unknown) {
        const value = input as {bid_id?: string};
        if (!value || typeof value.bid_id !== 'string' || !/^[0-9a-f-]{36}$/i.test(value.bid_id)) throw new Error('A valid bid ID is required');
        const r = await request<Review>(`/bids/${value.bid_id}`);
        return {bid_id:r.id,run_id:r.current_run_id,compliance_score:r.compliance_score,risk:r.risk_level,
          findings:r.compliance.map(rule=>({rule:rule.rule_code,status:rule.status,evidence:rule.evidence})),
          advisory:r.ai?.recommended_action,officer_decision:r.final_decision,is_mock:true};
      },
    },{signal:lifecycle.signal})).catch(()=>undefined);
  } catch { /* Browser support is optional; the regular interface remains available. */ }
  return () => lifecycle.abort();
}
