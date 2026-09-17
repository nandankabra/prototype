import { useState } from 'react';
import { ArrowRight, FileCheck2, Fingerprint, ShieldCheck, UserCheck, Workflow } from 'lucide-react';
import { post } from '../services/api';
import type { User } from '../types';
import { ErrorBox } from '../components/ui';

export default function Login({ onLogin }: {onLogin: (user: User, token: string) => void}) {
  const [email, setEmail] = useState(''), [password, setPassword] = useState(''), [name, setName] = useState(''), [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function submit() {
    setBusy(true); setError('');
    try { const result = await post<{user: User; access_token: string}>(register ? '/auth/register' : '/auth/login', register ? {name, email, password} : {email, password}); onLogin(result.user, result.access_token); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <div className="login-page"><aside className="login-story"><div className="brand"><div className="brand-mark"><ShieldCheck/></div><span>ByteCode <b>Verify</b></span></div><div className="login-story-main"><div className="eyebrow">PROCUREMENT, WITH CONFIDENCE</div><h1>Every bid.<br/>Every check.<br/><em>Evidence first.</em></h1><p>Bid verification and officer decision support for public procurement.</p><div className="login-flow">{[[FileCheck2, 'Tender-specific requirements'], [Fingerprint, 'Traceable evidence'], [UserCheck, 'Officer-led final action']].map(([Icon, label]) => { const I = Icon as typeof FileCheck2; return <div key={String(label)}><I size={23}/><span>{String(label)}</span><ArrowRight size={16}/></div>; })}</div></div></aside><main className="login-form-side"><div className="login-form"><span className="demo-chip">AUTHORISED ACCESS</span><h2>{register ? 'Create bidder account' : 'Sign in to your workspace'}</h2><p>Each source outcome retains its actual method, evidence, and timestamp.</p><ErrorBox message={error}/><form onSubmit={e=>{e.preventDefault(); void submit();}}>{register && <label>Organisation / bidder name<input value={name} onChange={e=>setName(e.target.value)} required minLength={3}/></label>}<label>Email<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required autoComplete="username"/></label><label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required minLength={register ? 12 : 1} autoComplete={register ? 'new-password' : 'current-password'}/></label><button className="button primary full" disabled={busy}>{register ? 'Create bidder account' : 'Sign in'} <ArrowRight size={17}/></button></form><button className="text-button admin-login" disabled={busy} onClick={()=>{setRegister(!register);setError('');}}>{register ? 'Use an existing account' : 'Register as a bidder'} <ArrowRight size={13}/></button><div className="login-note"><Workflow size={21}/><p>Procurement officers and auditors are provisioned through authorised organisation access.</p></div></div></main></div>;
}
