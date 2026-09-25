import { useState } from 'react';
import { ArrowRight, Eye, EyeOff, FileCheck2, Fingerprint, LoaderCircle, LockKeyhole, ShieldCheck, UserCheck } from 'lucide-react';
import { post } from '../services/api';
import type { User } from '../types';
import { ErrorBox } from '../components/ui';

export default function Login({ onLogin }: {onLogin: (user: User, token: string) => void}) {
  const [email, setEmail] = useState(''), [password, setPassword] = useState(''), [name, setName] = useState(''), [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [showPassword, setShowPassword] = useState(false);
  async function submit() {
    setBusy(true); setError('');
    try { const result = await post<{user: User; access_token: string}>(register ? '/auth/register' : '/auth/login', register ? {name, email, password} : {email, password}); onLogin(result.user, result.access_token); }
    catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <div className="login-page">
    <aside className="login-story">
      <div className="brand"><div className="brand-mark"><ShieldCheck/></div><span>ByteCode <b>Verify</b></span></div>
      <div className="login-story-main">
        <div className="eyebrow"><span className="live-dot"/> PROCUREMENT, WITH CONFIDENCE</div>
        <h1>Every bid.<br/>Every check.<br/><em>Evidence first.</em></h1>
        <p>A clearer path from submitted documents to informed procurement decisions.</p>
        <div className="login-flow">
          {[{icon:FileCheck2, label:'Review the requirements', detail:'Keep every check connected to its tender.'}, {icon:Fingerprint, label:'Follow the evidence', detail:'Trace findings back to their source.'}, {icon:UserCheck, label:'Decide with confidence', detail:'Your judgment. A complete audit trail.'}].map(({icon:Icon,label,detail},i) => <div key={label}><span className="login-step-icon"><Icon size={21}/></span><div><strong>{label}</strong><small>{detail}</small></div><span className="login-step-number">0{i+1}</span></div>)}
        </div>
      </div>
      <div className="login-footer"><ShieldCheck size={15}/><span>AI assists. Officers decide.</span><span>BYTECODE VERIFY</span></div>
    </aside>
    <main className="login-form-side"><div className="login-form">
      <span className="demo-chip"><LockKeyhole size={13}/> AUTHORISED WORKSPACE</span>
      <h2>{register ? 'Create your bidder account' : 'Welcome back.'}</h2>
      <p>{register ? 'Register your organisation to submit applications and supporting documents.' : 'Sign in to review applications, follow the evidence, and keep procurement moving.'}</p>
      <ErrorBox message={error}/>
      <form onSubmit={e=>{e.preventDefault(); void submit();}} aria-busy={busy}>
        {register && <label>Organisation / bidder name<input value={name} onChange={e=>setName(e.target.value)} required minLength={3} autoComplete="organization" placeholder="Your organisation name" disabled={busy}/></label>}
        <label>Email address<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required autoComplete="username" placeholder="you@organisation.com" disabled={busy}/></label>
        <label>Password<span className="password-field"><input type={showPassword ? 'text' : 'password'} value={password} onChange={e=>setPassword(e.target.value)} required minLength={register ? 12 : 1} autoComplete={register ? 'new-password' : 'current-password'} placeholder={register ? 'At least 12 characters' : 'Enter your password'} disabled={busy} aria-describedby={register ? 'password-hint' : undefined}/><button type="button" className="password-toggle" onClick={()=>setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}>{showPassword ? <EyeOff size={18}/> : <Eye size={18}/>}</button></span></label>
        {register && <small id="password-hint" className="field-hint">Use at least 12 characters for your password.</small>}
        <button className="button primary full" disabled={busy}>{busy ? <><LoaderCircle size={18} className="spin"/>{register ? 'Creating account…' : 'Signing in…'}</> : <>{register ? 'Create bidder account' : 'Sign in to workspace'}<ArrowRight size={17}/></>}</button>
      </form>
      <div className="login-register"><span>{register ? 'Already have an account?' : 'Applying for a tender?'}</span><button className="text-button" disabled={busy} onClick={()=>{setRegister(!register);setError('');setShowPassword(false);}}>{register ? 'Sign in' : 'Register as a bidder'}<ArrowRight size={14}/></button></div>
      <div className="login-note"><ShieldCheck size={20}/><p>Officer and auditor accounts are provided by your organisation’s administrator.</p></div>
    </div></main>
  </div>;
}
