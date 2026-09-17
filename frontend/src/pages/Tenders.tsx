import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Plus, Search, ShieldCheck, Upload } from 'lucide-react'
import type { Tender, User } from '../types'
import { formPost, post, useApi } from '../services/api'
import { Badge, BidTable, Empty, ErrorBox, Loading, Modal, PageHeading, Panel } from '../components/ui'

type Props = { user: User }

export function TenderList({ user }: Props) {
  const { data, error, loading, reload } = useApi<Tender[]>('/tenders')
  const [search, setSearch] = useState('')
  const [importOpen, setImportOpen] = useState(false)
  const canImport = user.role === 'PROCUREMENT_OFFICER' || user.role === 'ADMIN'
  const tenders = (data || []).filter((t) => `${t.title} ${t.external_bid_id || t.reference}`.toLowerCase().includes(search.toLowerCase()))

  return <div className="page">
    <PageHeading eyebrow="Procurement portfolio" title="Search GeM Tenders" description="Import official GeM tender documents and review extracted compliance requirements."
      actions={canImport ? <button className="btn primary" onClick={() => setImportOpen(true)}><Upload size={17} /> Import official GeM document</button> : undefined} />
    <Panel className="notice-panel"><ShieldCheck size={22} /><div><b>Official sources only</b><span>Use the public GeM bid-document page URL or a direct GeM PDF. Restricted pages, sign-in pages, and CAPTCHA-protected URLs cannot be imported.</span></div></Panel>
    <div className="toolbar"><label className="search"><Search size={19} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by tender title or GeM bid number" /></label></div>
    {loading && <Loading />}{error && <ErrorBox message={error} />}
    {!loading && !error && !tenders.length && <Empty title="No GeM tenders imported yet">{canImport ? <><span>Import the official GeM PDF to create a verified tender record.</span><br/><button className="btn primary" onClick={() => setImportOpen(true)}><Upload size={17} /> Import official GeM document</button></> : 'A procurement officer can import an official GeM tender document.'}</Empty>}
    {!!tenders.length && <Panel className="table-panel"><table><thead><tr><th>GeM tender</th><th>Organisation</th><th>Deadline</th><th>Requirements</th><th>Status</th><th /></tr></thead><tbody>{tenders.map((t) => <tr key={t.id}><td><b>{t.title}</b><small>{t.external_bid_id || t.reference}</small></td><td>{t.organisation || t.department || '—'}</td><td>{t.deadline || 'Not stated'}</td><td>{t.requirement_count ?? t.requirements?.length ?? 0}</td><td><Badge value={t.status} /></td><td><Link className="row-link" to={`/tenders/${t.id}`}>Review <ArrowRight size={16} /></Link></td></tr>)}</tbody></table></Panel>}
    {importOpen && <ImportTender onClose={() => setImportOpen(false)} onDone={() => { setImportOpen(false); reload() }} />}
  </div>
}

function ImportTender({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [externalBidId, setExternalBidId] = useState('')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [method, setMethod] = useState<'URL' | 'UPLOAD'>('URL')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try {
      if (method === 'UPLOAD') {
        if (!file) throw new Error('Choose the official GeM bid PDF before importing.')
        const form = new FormData(); form.append('external_bid_id', externalBidId); form.append('document', file)
        await formPost('/tenders/import/gem/upload', form)
      } else await post('/tenders/import/gem', { external_bid_id: externalBidId, official_document_url: url })
      onDone()
    }
    catch (err) { setError(err instanceof Error ? err.message : 'The GeM document could not be imported.') }
    finally { setBusy(false) }
  }
  return <Modal title="Import official GeM document" onClose={onClose}>
    <form className="form-stack" onSubmit={submit}>
      <p className="muted">Use a public GeM document URL, or download the official bid PDF normally from GeM and upload it here. No right-click is needed.</p>
      <div className="segmented"><button type="button" className={method === 'URL' ? 'active' : ''} onClick={() => setMethod('URL')}>Use public URL</button><button type="button" className={method === 'UPLOAD' ? 'active' : ''} onClick={() => setMethod('UPLOAD')}>Upload downloaded PDF</button></div>
      <label>GeM bid number<input required value={externalBidId} onChange={(e) => setExternalBidId(e.target.value)} placeholder="GEM/2026/B/1234567" /></label>
      {method === 'URL' ? <label>Official GeM document URL<input required type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://bidplus-global.gem.gov.in/showbidDocument/..." /></label> : <label>Official GeM bid PDF<input required type="file" accept="application/pdf,.pdf" onChange={(e) => setFile(e.target.files?.[0] || null)} /></label>}
      {error && <ErrorBox message={error} />}
      <div className="modal-actions"><button type="button" className="btn secondary" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy}>{busy ? 'Importing and extracting…' : 'Import and extract requirements'}</button></div>
    </form>
  </Modal>
}

export function TenderDetail({ user }: Props) {
  const { tenderId } = useParams()
  const { data: tender, error, loading, reload } = useApi<Tender>(`/tenders/${tenderId}`)
  const [applicationOpen, setApplicationOpen] = useState(false)
  if (loading) return <Loading />
  if (error || !tender) return <div className="page"><ErrorBox message={error || 'Tender not found'} /></div>
  const canApply = user.role === 'BIDDER'
  const requirements = tender.requirements || []
  return <div className="page">
    <Link className="back-link" to="/tenders"><ArrowLeft size={17} /> Search GeM Tenders</Link>
    <PageHeading eyebrow="Official GeM tender" title={tender.title} description={`${tender.external_bid_id || tender.reference}${tender.organisation ? ` · ${tender.organisation}` : ''}`} actions={canApply ? <button className="btn primary" onClick={() => setApplicationOpen(true)}><Plus size={17} /> Submit bidder application</button> : undefined} />
    <div className="detail-grid"><Panel><span className="eyebrow">Tender status</span><h3><Badge value={tender.status} /></h3><dl><dt>Deadline</dt><dd>{tender.deadline || 'Not stated'}</dd><dt>Source</dt><dd>{tender.source_url ? <a href={tender.source_url} target="_blank" rel="noreferrer">Official GeM document</a> : 'Recorded at import'}</dd><dt>Department</dt><dd>{tender.department || '—'}</dd></dl></Panel><Panel><span className="eyebrow">Document record</span><h3>{tender.tender_documents?.length || 0} source document(s)</h3><p className="muted">Every requirement below retains its extracted source text, page reference, and confidence score.</p></Panel></div>
    <Panel><div className="section-heading"><div><span className="eyebrow">Requirement checklist</span><h2>Extracted tender requirements</h2></div><span className="muted">{requirements.length} item(s)</span></div>
      {!requirements.length ? <Empty title="No requirements were extracted">Review the original document or import a clearer official GeM PDF.</Empty> : <div className="requirements">{requirements.map((r) => <article className="requirement" key={r.id}><div><b>{r.label}</b><p>{r.source_text}</p><small>{r.source_page ? `Page ${r.source_page} · ` : ''}{Math.round((r.confidence || 0) * 100)}% extraction confidence</small></div><div><Badge value={r.mandatory ? 'MANDATORY' : 'OPTIONAL'} />{r.accepted_evidence?.length ? <small className="evidence">Evidence: {r.accepted_evidence.join(', ')}</small> : null}</div></article>)}</div>}</Panel>
    <Panel><div className="section-heading"><div><span className="eyebrow">Bidder applications</span><h2>Compliance review queue</h2></div><span className="muted">{tender.bids?.length || 0} application(s)</span></div><BidTable bids={tender.bids || []} /></Panel>
    {applicationOpen && <CreateApplication tender={tender} onClose={() => setApplicationOpen(false)} onDone={() => { setApplicationOpen(false); reload() }} />}
  </div>
}

function CreateApplication({ tender, onClose, onDone }: { tender: Tender; onClose: () => void; onDone: () => void }) {
  const [name, setName] = useState(''); const [pan, setPan] = useState(''); const [gstin, setGstin] = useState(''); const [udyam, setUdyam] = useState(''); const [address, setAddress] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError('')
    try { await post('/bids', { tender_id: tender.id, name, pan: pan.toUpperCase(), gstin: gstin.toUpperCase(), udyam, address }); onDone() }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not create application.') } finally { setBusy(false) }
  }
  return <Modal title="Submit bidder application" onClose={onClose}><form className="form-stack" onSubmit={submit}>
    <p className="muted">Create the bidder application, then upload its supporting documents from the review workspace.</p>
    <label>Bidder organisation name<input required minLength={3} value={name} onChange={(e) => setName(e.target.value)} /></label>
    <label>PAN<input required value={pan} onChange={(e) => setPan(e.target.value)} placeholder="ABCDE1234F" /></label>
    <label>GSTIN<input required value={gstin} onChange={(e) => setGstin(e.target.value)} placeholder="27ABCDE1234F1Z5" /></label>
    <label>Udyam registration <span className="muted">(optional)</span><input value={udyam} onChange={(e) => setUdyam(e.target.value)} /></label>
    <label>Registered address <textarea value={address} onChange={(e) => setAddress(e.target.value)} /></label>
    {error && <ErrorBox message={error} />}<div className="modal-actions"><button type="button" className="btn secondary" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy}>{busy ? 'Saving…' : 'Create application'}</button></div>
  </form></Modal>
}
