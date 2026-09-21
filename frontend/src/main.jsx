import React, { useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'
import './toast.css'

async function request(path, options) {
  const response = await fetch(path, options)
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(typeof body.detail === 'string' ? body.detail : `Error HTTP ${response.status}`)
    error.status = response.status
    throw error
  }
  return body
}

const money = (value, currency = 'USD') => new Intl.NumberFormat('es-CO', { style: 'currency', currency }).format(Number(value))
const stateName = { PENDIENTE: 'Pendiente', PROCESSING: 'Procesando', COMPLETADO: 'Sincronizado', FALLIDO: 'Falló' }

function App() {
  const [accounts, setAccounts] = useState([])
  const [apiOnline, setApiOnline] = useState(false)
  const [aiOnline, setAiOnline] = useState(false)
  const [form, setForm] = useState({ source_account: '', destination_account: '', amount: '', currency: 'USD' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [transactionId, setTransactionId] = useState('')
  const [lookupId, setLookupId] = useState('')
  const [lookupVersion, setLookupVersion] = useState(0)
  const [transaction, setTransaction] = useState(null)
  const [recommendation, setRecommendation] = useState(null)
  const [recommendationOpen, setRecommendationOpen] = useState(false)
  const shownRecommendationId = useRef(null)
  const [etl, setEtl] = useState(null)
  const [etlBusy, setEtlBusy] = useState(false)
  const [etlError, setEtlError] = useState('')
  const [etlTab, setEtlTab] = useState('valid')

  const refreshAccounts = () => request('/api/accounts').then(rows => {
    setAccounts(rows)
    setForm(current => ({
      ...current,
      source_account: rows.some(row => row.account_number === current.source_account) ? current.source_account : (rows[0]?.account_number || ''),
      destination_account: rows.some(row => row.account_number === current.destination_account) ? current.destination_account : (rows[1]?.account_number || ''),
    }))
  }).catch(err => setError(err.message))

  useEffect(() => {
    request('/api/health').then(() => setApiOnline(true)).catch(() => setApiOnline(false))
    request('/ai/health').then(() => setAiOnline(true)).catch(() => setAiOnline(false))
    refreshAccounts()
  }, [])

  useEffect(() => {
    if (!transactionId) return
    let active = true
    let attempts = 0
    const poll = async () => {
      attempts += 1
      try {
        const detail = await request(`/api/transactions/${transactionId}`)
        if (active) setTransaction(detail)
      } catch (err) {
        if (active) setError(err.message)
      }
      try {
        const result = await request(`/api/transactions/${transactionId}/recommendation`)
        if (active) {
          setRecommendation(result)
          if (shownRecommendationId.current !== result.transaction_id) {
            shownRecommendationId.current = result.transaction_id
            setRecommendationOpen(true)
          }
        }
      } catch (err) {
        if (active && err.status !== 404) setError(err.message)
      }
    }
    poll()
    const interval = setInterval(() => { if (attempts >= 30) clearInterval(interval); else poll() }, 2000)
    return () => { active = false; clearInterval(interval) }
  }, [transactionId, lookupVersion])

  useEffect(() => {
    if (!recommendationOpen) return
    const timeout = setTimeout(() => setRecommendationOpen(false), 12000)
    return () => clearTimeout(timeout)
  }, [recommendationOpen])

  async function submit(event) {
    event.preventDefault()
    setBusy(true); setError(''); setTransactionId(''); setRecommendation(null); setRecommendationOpen(false); setTransaction(null)
    try {
      const key = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`
      const result = await request('/api/transactions', {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
        body: JSON.stringify({ ...form, amount: form.amount.trim() }),
      })
      setTransactionId(String(result.transaction_id))
      setLookupId(String(result.transaction_id))
      setForm(current => ({ ...current, amount: '' }))
      refreshAccounts()
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  function lookup(event) {
    event.preventDefault()
    if (!lookupId.trim()) return
    setError(''); setTransaction(null); setRecommendation(null); setRecommendationOpen(false)
    setTransactionId(lookupId.trim())
    setLookupVersion(version => version + 1)
  }

  async function runEtl() {
    setEtlBusy(true); setEtlError('')
    try { setEtl(await request('/api/etl/run', { method: 'POST' })) }
    catch (err) { setEtlError(err.message) }
    finally { setEtlBusy(false) }
  }

  useEffect(() => {
    if (!etl?.run_id || etl.recommendation_status === 'COMPLETADO' || etl.recommendation_status === 'FALLIDO') return
    const interval = setInterval(() => {
      request(`/api/etl/runs/${etl.run_id}`).then(setEtl).catch(err => setEtlError(err.message))
    }, 2000)
    return () => clearInterval(interval)
  }, [etl?.run_id, etl?.recommendation_status])

  const rows = etl?.[etlTab] || []
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon">S</div><div><strong>smartbancs</strong><span>OPERATIONS</span></div></div>
      <div className="side-label">ESPACIO DE TRABAJO</div>
      <a className="nav active" href="#overview"><span>▦</span> Resumen</a>
      <a className="nav" href="#transfer"><span>↗</span> Transferencias</a>
      <a className="nav" href="#etl"><span>▤</span> Calidad de datos</a>
      <div className="side-bottom"><div className="side-label">SERVICIOS</div><div className="service"><i className={apiOnline ? 'dot' : 'dot offline'} /> API de transacciones</div><div className="service"><i className={aiOnline ? 'dot' : 'dot offline'} /> Servicio de IA</div><div className="sidebar-note">Entorno de demostración<br />SmartBancs MVP</div></div>
    </aside>

    <main id="overview" className="main">
      <header className="topbar"><span>Panel de operaciones <b>/</b> Resumen</span><span className="environment"><i className="dot" /> ENTORNO LOCAL</span></header>
      <div className="content">
        <div className="heading"><div><div className="eyebrow">SMARTBANCS / MVP</div><h1>Control de operaciones</h1><p>Transferencias, recomendaciones y calidad de datos en un solo lugar.</p></div><span className="date">● &nbsp; Panel en tiempo real</span></div>

        <section className="stats">
          <div className="stat"><span>CUENTAS DISPONIBLES</span><strong>{accounts.length}</strong><small>Datos actuales de PostgreSQL</small></div>
          <div className="stat"><span>ÚLTIMA TRANSFERENCIA</span><strong>{transaction?.transaction_id ? `#${transaction.transaction_id}` : '—'}</strong><small>{transaction?.status === 'COMPLETADA' ? 'Movimiento confirmado' : 'Sin consulta activa'}</small></div>
          <div className="stat"><span>SINCRONIZACIÓN BANCS</span><strong className="stat-status">{stateName[transaction?.bancs_sync_status] || '—'}</strong><small>Se actualiza cada 2 segundos</small></div>
          <button type="button" className="stat recommendation-stat" disabled={!recommendation} onClick={() => setRecommendationOpen(true)}><span>RECOMENDACIÓN IA</span><strong className="stat-status">{recommendation ? 'Disponible' : transaction?.recommendation_status === 'FALLIDO' ? 'Falló' : transaction ? 'En proceso' : '—'}</strong><small>{recommendation ? 'Haz clic para verla de nuevo ↗' : transaction?.recommendation_status === 'FALLIDO' ? 'No se pudo guardar la recomendación' : 'Generada por el worker de IA'}</small></button>
        </section>

        <div className="grid">
          <section id="transfer" className="card transfer-card"><div className="card-header"><div><div className="eyebrow">OPERACIÓN</div><h2>Nueva transferencia</h2><p>Transfiere fondos entre las cuentas disponibles.</p></div><span className="card-icon">↗</span></div>
            <form onSubmit={submit}>
              <div className="field-row"><label>Cuenta origen<select value={form.source_account} onChange={e => setForm({ ...form, source_account: e.target.value })}>{accounts.map(a => <option key={a.account_number} value={a.account_number}>{a.account_number} · {money(a.balance, a.currency)}</option>)}</select></label><label>Cuenta destino<select value={form.destination_account} onChange={e => setForm({ ...form, destination_account: e.target.value })}>{accounts.map(a => <option key={a.account_number} value={a.account_number}>{a.account_number} · {money(a.balance, a.currency)}</option>)}</select></label></div>
              <div className="field-row"><label>Monto<input required type="number" min="0.01" step="0.01" placeholder="0.00" value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })} /></label><label>Moneda<select value={form.currency} onChange={e => setForm({ ...form, currency: e.target.value })}><option>USD</option><option>EUR</option></select></label></div>
              {error && <div className="alert">{error}</div>}
              <button className="primary" disabled={busy || accounts.length < 2 || form.source_account === form.destination_account}>{busy ? 'Procesando…' : 'Enviar transferencia'} <span>→</span></button>
              {form.source_account === form.destination_account && <small className="hint">Selecciona dos cuentas distintas.</small>}
            </form>
          </section>

          <section className="card account-card"><div className="card-header"><div><div className="eyebrow">SALDOS</div><h2>Cuentas</h2><p>Saldo después de las operaciones confirmadas.</p></div><span className="card-icon">▤</span></div><div className="accounts">{accounts.map(a => <div className="account" key={a.account_number}><div className="account-symbol">{a.account_number.slice(-2)}</div><div><strong>{a.account_number}</strong><small>Cuenta {a.currency}</small></div><b>{money(a.balance, a.currency)}</b></div>)}{!accounts.length && <p className="empty">No se pudieron cargar las cuentas.</p>}</div><button className="subtle" onClick={refreshAccounts}>Actualizar saldos ↻</button></section>
        </div>

        <div className="grid lower">
          <section className="card"><div className="card-header"><div><div className="eyebrow">SEGUIMIENTO</div><h2>Estado de transacción</h2><p>Consulta una operación y su recomendación.</p></div><span className="card-icon">⌕</span></div><form className="lookup" onSubmit={lookup}><input type="number" min="1" placeholder="ID de transacción" value={lookupId} onChange={e => setLookupId(e.target.value)} /><button type="submit">Consultar</button></form>
            {transaction ? <div className="detail"><div><span>Estado local</span><strong className="success">{transaction.status}</strong></div><div><span>Sincronización Bancs</span><strong>{stateName[transaction.bancs_sync_status] || transaction.bancs_sync_status}</strong></div><div><span>Referencia Bancs</span><strong>{transaction.bancs_reference || 'Pendiente'}</strong></div><div><span>Movimiento</span><strong>{transaction.source_account} → {transaction.destination_account}</strong></div><div><span>Importe</span><strong>{money(transaction.amount, transaction.currency)}</strong></div></div> : <div className="empty-box">Introduce un ID o realiza una transferencia para ver el seguimiento.</div>}
          </section>

          <section id="etl" className="card"><div className="card-header"><div><div className="eyebrow">PIPELINE ETL</div><h2>Calidad de datos</h2><p>Procesa el CSV de ejemplo incluido en el proyecto.</p></div><span className="card-icon">◇</span></div><button className="outline" onClick={runEtl} disabled={etlBusy}>{etlBusy ? 'Procesando…' : 'Ejecutar ETL de muestra'} <span>→</span></button>{etlError && <div className="alert">{etlError}</div>}
            {etl ? <><div className="etl-summary"><div><strong>{etl.summary.input_rows}</strong><small>Registros</small></div><div><strong>{etl.summary.valid_rows}</strong><small>Válidos</small></div><div><strong>{etl.summary.rejected_rows}</strong><small>Rechazados</small></div><div><strong>{etl.summary.duplicates}</strong><small>Duplicados</small></div></div><div className="empty-box etl-recommendation"><strong>Recomendación de calidad de datos</strong><p>{etl.recommendation || (etl.recommendation_status === 'FALLIDO' ? 'No se pudo generar la recomendación. Ejecuta el ETL de nuevo.' : 'Analizando los motivos de rechazo…')}</p></div><div className="tabs"><button className={etlTab === 'valid' ? 'selected' : ''} onClick={() => setEtlTab('valid')}>Válidos</button><button className={etlTab === 'rejected' ? 'selected' : ''} onClick={() => setEtlTab('rejected')}>Rechazados</button></div><div className="table-wrap"><table><thead><tr><th>ID</th><th>Monto</th><th>Moneda</th><th>Fecha</th></tr></thead><tbody>{rows.map((row, i) => <tr key={`${row.transaction_id}-${i}`}><td>{row.transaction_id}</td><td>{row.amount || '—'}</td><td>{row.currency}</td><td>{row.date || '—'}</td></tr>)}</tbody></table></div></> : <div className="empty-box etl-empty">El resumen de datos aparecerá aquí después de ejecutar el ETL.</div>}
          </section>
        </div>
        <footer>SmartBancs MVP <span>API · Outbox · IA · ETL</span></footer>
      </div>
    </main>
    {recommendationOpen && recommendation && <aside className="recommendation-toast" role="status" aria-live="polite" aria-label="Recomendación de IA"><div className="toast-symbol">✦</div><div className="toast-content"><strong>Recomendación de IA</strong><p>{recommendation.recommendation}</p><small>Transacción #{recommendation.transaction_id} · {recommendation.model_version}</small></div><button type="button" className="toast-close" aria-label="Cerrar recomendación" onClick={() => setRecommendationOpen(false)}>×</button></aside>}
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
