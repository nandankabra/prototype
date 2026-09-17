import { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { Activity, BookOpenCheck, ChevronDown, FileStack, Fingerprint, LayoutDashboard, LogOut, Menu, Settings2, ShieldCheck, X } from 'lucide-react';
import Login from './pages/Login';
const Dashboard = lazy(() => import('./pages/Dashboard'));
import { TenderList, TenderDetail } from './pages/Tenders';
import BidList from './pages/BidList';
import BidReview from './pages/BidReview';
import AuditTrail from './pages/AuditTrail';
import AdminRules from './pages/AdminRules';
import { getToken, request, setToken } from './services/api';
import { Loading, pretty } from './components/ui';
import type { User } from './types';
import { registerReviewTool } from './services/webmcp';
const links = [{to:'/', label:'Dashboard', icon:LayoutDashboard}, {to:'/tenders',label:'Search GeM Tenders',icon:FileStack}, {to:'/bids',label:'Applications',icon:BookOpenCheck}, {to:'/verification',label:'Verification',icon:ShieldCheck}, {to:'/risk',label:'Risk Intelligence',icon:Activity}, {to:'/audit',label:'Audit Trail',icon:Fingerprint}, {to:'/rules',label:'Rules',icon:Settings2}];
function Workspace({user, logout}:{user:User; logout:()=>void}) {
  const [mobile,setMobile] = useState(false); const location=useLocation();
  useEffect(()=>setMobile(false),[location.pathname]);
  useEffect(registerReviewTool, []);
  return <div className="app-shell"><aside className={`sidebar ${mobile ? 'open' : ''}`}><NavLink to="/" className="brand"><div className="brand-mark"><ShieldCheck size={25}/></div><span>ByteCode <b>Verify</b></span></NavLink><div className="workspace-label">PROCUREMENT WORKSPACE</div><nav>{links.map(l=><NavLink end={l.to==='/'} className={({isActive})=>`nav-link ${isActive?'active':''}`} to={l.to} key={l.to}><l.icon size={19}/>{l.label}</NavLink>)}</nav><div className="sidebar-bottom"><div className="authority-note"><ShieldCheck size={22}/><strong>AI assists. Officers decide.</strong><p>Evidence-backed verification.<br/>Human-led procurement.</p></div></div></aside>{mobile && <button className="sidebar-overlay" onClick={()=>setMobile(false)} aria-label="Close navigation"/>}<div className="main-shell"><header className="topbar"><div className="topbar-context"><button className="icon-button mobile-menu" onClick={()=>setMobile(!mobile)} aria-label="Toggle navigation">{mobile?<X size={21}/>:<Menu size={21}/>}</button><span className="org-monogram">GV</span><div><strong>Procurement Verification</strong><small>Authorised workspace</small></div><ChevronDown size={14}/></div><div className="topbar-right"><span className="environment-tag"><span className="live-dot"/> Controlled environment</span><div className="topbar-separator"/><div className="user-avatar">{user.name.split(' ').map(n=>n[0]).slice(0,2).join('')}</div><div className="user-info"><strong>{user.name}</strong><span>{pretty(user.role)}</span></div><button className="icon-button" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={17}/></button></div></header><main className="workspace-main"><Suspense fallback={<Loading/>}><Routes><Route path="/" element={<Dashboard/>}/><Route path="/tenders" element={<TenderList user={user}/>}/><Route path="/tenders/:tenderId" element={<TenderDetail user={user}/>}/><Route path="/bids" element={<BidList/>}/><Route path="/bids/:bidId" element={<BidReview user={user}/>}/><Route path="/verification" element={<BidList mode="verification"/>}/><Route path="/risk" element={<BidList mode="risk"/>}/><Route path="/audit" element={<AuditTrail/>}/><Route path="/rules" element={<AdminRules user={user}/>}/><Route path="*" element={<div className="empty"><h1>Page not found</h1><NavLink to="/">Return to dashboard</NavLink></div>}/></Routes></Suspense></main><footer className="workspace-footer"><span>ByteCode Verify · Procurement decision support</span><span>Government checks are shown only with their actual verification method and status</span></footer></div></div>;
}
export default function App(){
  const [user,setUser]=useState<User|null>(null),[ready,setReady]=useState(false);
  useEffect(()=>{if(getToken()) request<User>('/auth/me').then(setUser).catch(()=>setToken(null)).finally(()=>setReady(true)); else setReady(true);},[]);
  if(!ready)return <Loading/>;
  return <BrowserRouter>{user?<Workspace user={user} logout={()=>{setToken(null);setUser(null);}}/>:<Login onLogin={(u,t)=>{setToken(t);setUser(u);}}/>}</BrowserRouter>;
}
