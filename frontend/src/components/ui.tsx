import { useEffect, useRef, type ReactNode } from 'react';
import { AlertCircle, Check, ChevronRight, LoaderCircle, ShieldCheck, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Bid, Run } from '../types';
export const pretty = (value?: string | null) => (value || 'Not assessed').replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
export const dateTime = (value?: string) => value ? new Date(value).toLocaleString('en-IN', {day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'}) : '—';
export const percent = (value: number) => `${Math.round(value * 100)}%`;
export function Badge({ value }: { value?: string | null }) {
  const status = value || 'UNASSESSED';
  const tone = /^(VERIFIED|MATCH|PASS|LOW|QUALIFIED|COMPLETED|ACTIVE)$/.test(status) ? 'green' : /MISMATCH|FAIL|CRITICAL|DISQUALIFIED|EXPIRED/.test(status) ? 'red' : /HIGH|MEDIUM|REVIEW|CLARIFICATION|MISSING|UNAVAILABLE|PENDING/.test(status) ? 'amber' : 'neutral';
  return <span className={`badge ${tone}`}><span className="badge-dot"/>{pretty(status)}</span>;
}
export function MockLabel() { return <span className="mock-label"><ShieldCheck size={13}/> MOCK AUTHORISED SOURCE — DEMO</span>; }
export function ErrorBox({ message }: {message: string}) { return message ? <div role="alert" className="error-box"><AlertCircle size={18}/>{message}</div> : null; }
export function Loading() { return <div className="loading"><LoaderCircle className="spin" size={22}/> Loading workspace…</div>; }
export function Empty({ title, children }: {title: string; children?: ReactNode}) { return <div className="empty"><ShieldCheck size={30}/><h3>{title}</h3><p>{children}</p></div>; }
export function PageHeading({ eyebrow, title, description, actions }: {eyebrow?: string; title: string; description?: string; actions?: ReactNode}) {
  return <div className="page-heading"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{description && <p>{description}</p>}</div><div className="heading-actions">{actions}</div></div>;
}
export function Panel({ title, subtitle, action, children, className = '' }: {title?: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string}) {
  return <section className={`panel ${className}`}>{title && <div className="panel-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>}{children}</section>;
}
export function Modal({ title, children, onClose, wide = false }: {title: string; children: ReactNode; onClose: () => void; wide?: boolean}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const el = ref.current; el?.showModal(); return () => el?.close(); }, []);
  return <dialog ref={ref} className={`modal ${wide ? 'wide' : ''}`} onCancel={onClose} onClick={e => { if (e.target === ref.current) onClose(); }}><div className="modal-head"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close dialog"><X size={21}/></button></div>{children}</dialog>;
}
export function BidTable({ bids, compact = false }: {bids: Bid[]; compact?: boolean}) {
  if (!bids.length) return <Empty title="No bids yet">Add a bidder to start reviewing documents.</Empty>;
  return <div className="table-scroll"><table><thead><tr><th>Bidder / tender</th><th>Compliance</th><th>Risk level</th>{!compact && <th>Officer decision</th>}<th>Review</th></tr></thead><tbody>{bids.map(b => <tr key={b.id}><td><Link className="company-link" to={`/bids/${b.id}`}><span className="company-avatar">{b.bidder.name.split(' ').slice(0,2).map(w=>w[0]).join('')}</span><span><strong>{b.bidder.name}</strong><small>{b.tender.reference}</small></span></Link></td><td><div className="score-inline"><strong>{b.compliance_score ?? '—'}</strong><small>/100</small></div><div className="mini-track"><span style={{width: `${b.compliance_score || 0}%`}}/></div></td><td><Badge value={b.risk_level}/></td>{!compact && <td><Badge value={b.final_decision || b.status}/></td>}<td><Link to={`/bids/${b.id}`} className="table-action" aria-label={`Review ${b.bidder.name}`}>View <ChevronRight size={15}/></Link></td></tr>)}</tbody></table></div>;
}
export function ProcessingTimeline({ run }: {run: Run | null}) {
  if (!run) return <Empty title="Ready to verify">Start a review to process the submitted documents.</Empty>;
  return <div className="processing-timeline" aria-live="polite">{run.stages.map((stage, i) => <div className={`stage ${stage.status.toLowerCase()}`} key={stage.name}><span className="stage-marker">{stage.status === 'COMPLETED' ? <Check size={14}/> : stage.status === 'RUNNING' ? <LoaderCircle size={14} className="spin"/> : i+1}</span><div><strong>{stage.name}</strong><p>{stage.detail || pretty(stage.status)}</p>{stage.completed_at && <small>{dateTime(stage.completed_at)}</small>}</div></div>)}{run.error && <ErrorBox message={run.error}/>}</div>;
}
