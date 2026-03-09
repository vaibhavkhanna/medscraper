import { useState, useEffect, useRef } from 'react'

const API = '/api'

// ── API helpers ────────────────────────────────────────────────────────────────
const api = {
  startScrape: (url, page_cap) =>
    fetch(`${API}/scrape`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, page_cap }),
    }).then(r => r.json()),

  getJob: (id) => fetch(`${API}/jobs/${id}`).then(r => r.json()),
  listJobs: () => fetch(`${API}/jobs`).then(r => r.json()),
  deleteJob: (id) => fetch(`${API}/jobs/${id}`, { method: 'DELETE' }).then(r => r.json()),
  getJobDoctors: (id) => fetch(`${API}/jobs/${id}/doctors`).then(r => r.json()),
  downloadUrl: (id) => `${API}/jobs/${id}/download`,
}

// ── Styles ─────────────────────────────────────────────────────────────────────
const styles = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --ink: #0e0e0e;
    --paper: #f5f0e8;
    --paper2: #ede8de;
    --red: #c0392b;
    --red-light: #e8d5d3;
    --green: #1a7a4a;
    --green-light: #d3e8dc;
    --amber: #b8860b;
    --amber-light: #f0e6c0;
    --border: #c8c0b0;
    --mono: 'IBM Plex Mono', monospace;
    --serif: 'DM Serif Display', serif;
    --sans: 'Instrument Sans', sans-serif;
  }

  body {
    background: var(--paper);
    color: var(--ink);
    font-family: var(--sans);
    min-height: 100vh;
    font-size: 15px;
  }

  /* ── Header ── */
  .header {
    border-bottom: 2px solid var(--ink);
    padding: 0 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 64px;
    background: var(--paper);
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .logo {
    font-family: var(--serif);
    font-size: 24px;
    letter-spacing: -0.5px;
  }

  .logo span {
    color: var(--red);
    font-style: italic;
  }

  .header-tag {
    font-family: var(--mono);
    font-size: 11px;
    border: 1px solid var(--border);
    padding: 4px 10px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  /* ── Layout ── */
  .container {
    max-width: 1100px;
    margin: 0 auto;
    padding: 40px 24px;
  }

  /* ── Hero ── */
  .hero {
    margin-bottom: 48px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 40px;
  }

  .hero h1 {
    font-family: var(--serif);
    font-size: clamp(36px, 5vw, 56px);
    line-height: 1.05;
    letter-spacing: -1px;
    margin-bottom: 12px;
  }

  .hero h1 em {
    color: var(--red);
    font-style: italic;
  }

  .hero-sub {
    color: #666;
    font-size: 15px;
    max-width: 560px;
    line-height: 1.6;
  }

  /* ── Form card ── */
  .card {
    background: white;
    border: 2px solid var(--ink);
    padding: 28px 32px;
    margin-bottom: 24px;
    box-shadow: 5px 5px 0 var(--ink);
  }

  .card-title {
    font-family: var(--mono);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #888;
    margin-bottom: 18px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 10px;
  }

  .form-row {
    display: flex;
    gap: 12px;
    align-items: flex-end;
  }

  .form-group {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .form-group.narrow { flex: 0 0 140px; }

  label {
    font-size: 12px;
    font-family: var(--mono);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #555;
  }

  input[type="text"], input[type="number"] {
    font-family: var(--mono);
    font-size: 13px;
    padding: 10px 14px;
    border: 2px solid var(--ink);
    background: var(--paper);
    color: var(--ink);
    outline: none;
    width: 100%;
    transition: background 0.15s;
  }

  input:focus {
    background: white;
  }

  .btn {
    font-family: var(--mono);
    font-size: 13px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 11px 24px;
    border: 2px solid var(--ink);
    background: var(--ink);
    color: var(--paper);
    cursor: pointer;
    transition: all 0.1s;
    white-space: nowrap;
  }

  .btn:hover { background: #333; }
  .btn:active { transform: translate(2px, 2px); }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

  .btn-ghost {
    background: transparent;
    color: var(--ink);
  }

  .btn-ghost:hover { background: var(--paper2); }

  .btn-red {
    background: var(--red);
    border-color: var(--red);
    color: white;
  }
  .btn-red:hover { background: #a93226; }

  .btn-sm {
    padding: 6px 14px;
    font-size: 11px;
  }

  /* ── Jobs list ── */
  .jobs-grid {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .job-card {
    background: white;
    border: 2px solid var(--ink);
    padding: 20px 24px;
    box-shadow: 4px 4px 0 var(--ink);
    animation: slideIn 0.2s ease;
  }

  @keyframes slideIn {
    from { opacity: 0; transform: translateY(-8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .job-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 14px;
  }

  .job-url {
    font-family: var(--mono);
    font-size: 13px;
    font-weight: 500;
    word-break: break-all;
    flex: 1;
  }

  .badge {
    font-family: var(--mono);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 3px 10px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .badge-pending { background: var(--amber-light); color: var(--amber); border: 1px solid var(--amber); }
  .badge-running { background: #dff0ff; color: #1a5fa8; border: 1px solid #1a5fa8; }
  .badge-done { background: var(--green-light); color: var(--green); border: 1px solid var(--green); }
  .badge-failed { background: var(--red-light); color: var(--red); border: 1px solid var(--red); }

  .job-stats {
    display: flex;
    gap: 24px;
    margin-bottom: 14px;
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .stat-val {
    font-family: var(--mono);
    font-size: 20px;
    font-weight: 500;
    line-height: 1;
  }

  .stat-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #888;
  }

  /* Progress bar */
  .progress-wrap {
    background: var(--paper2);
    height: 4px;
    margin-bottom: 14px;
    overflow: hidden;
  }

  .progress-bar {
    height: 100%;
    background: var(--ink);
    transition: width 0.3s ease;
  }

  .progress-bar.done { background: var(--green); }
  .progress-bar.failed { background: var(--red); }

  /* Log */
  .log-toggle {
    font-family: var(--mono);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #888;
    cursor: pointer;
    border: none;
    background: none;
    padding: 0;
    margin-bottom: 8px;
    text-decoration: underline;
  }

  .log-box {
    background: var(--paper2);
    border: 1px solid var(--border);
    padding: 10px 12px;
    max-height: 160px;
    overflow-y: auto;
    font-family: var(--mono);
    font-size: 11px;
    line-height: 1.7;
    color: #444;
  }

  .log-entry { word-break: break-all; }
  .log-entry.err { color: var(--red); }

  /* Results table */
  .results-section {
    margin-top: 10px;
  }

  .results-toggle {
    font-family: var(--mono);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #555;
    cursor: pointer;
    border: none;
    background: none;
    padding: 0;
    margin-bottom: 6px;
    text-decoration: underline;
  }

  .results-table-wrap {
    border: 1px solid var(--border);
    background: var(--paper2);
    padding: 8px;
    max-height: 260px;
    overflow: auto;
  }

  .results-table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--mono);
    font-size: 11px;
  }

  .results-table thead {
    position: sticky;
    top: 0;
    background: #e0d8c8;
    z-index: 1;
  }

  .results-table th,
  .results-table td {
    padding: 4px 6px;
    border-bottom: 1px solid #d4cbb8;
    text-align: left;
    white-space: nowrap;
  }

  .results-table th {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    font-size: 10px;
  }

  .results-table td {
    font-size: 11px;
  }

  .results-loading,
  .results-empty,
  .results-note {
    font-family: var(--mono);
    font-size: 11px;
    color: #666;
    margin-top: 4px;
  }

  .job-actions {
    display: flex;
    gap: 8px;
    margin-top: 14px;
    align-items: center;
  }

  .pulsedot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #1a5fa8;
    animation: pulse 1.2s ease-in-out infinite;
    margin-right: 6px;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.7); }
  }

  .empty-state {
    text-align: center;
    padding: 60px 24px;
    border: 2px dashed var(--border);
    color: #aaa;
  }

  .empty-icon {
    font-size: 48px;
    display: block;
    margin-bottom: 12px;
  }

  .empty-state p {
    font-family: var(--mono);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .section-label {
    font-family: var(--mono);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #888;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .section-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }

  .error-msg {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--red);
    background: var(--red-light);
    padding: 8px 12px;
    border: 1px solid var(--red);
    margin-top: 8px;
  }

  @media (max-width: 600px) {
    .header { padding: 0 16px; }
    .container { padding: 24px 16px; }
    .form-row { flex-direction: column; }
    .form-group.narrow { flex: 1; }
    .card { padding: 20px 16px; box-shadow: 3px 3px 0 var(--ink); }
    .job-stats { gap: 16px; }
  }
`

// ── Components ─────────────────────────────────────────────────────────────────
function JobCard({ job, onDelete, onRefresh }) {
  const [showLog, setShowLog] = useState(false)
  const logRef = useRef(null)
  const [showResults, setShowResults] = useState(false)
  const [doctors, setDoctors] = useState([])
  const [loadingDoctors, setLoadingDoctors] = useState(false)
  const [resultsError, setResultsError] = useState('')
  const isRunning = job.status === 'running' || job.status === 'pending'

  useEffect(() => {
    if (showLog && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [job.log, showLog])

  const handleToggleResults = async () => {
    const next = !showResults
    setShowResults(next)

    if (next && doctors.length === 0 && !loadingDoctors) {
      setLoadingDoctors(true)
      setResultsError('')
      try {
        const data = await api.getJobDoctors(job.job_id)
        setDoctors(data || [])
      } catch (e) {
        setResultsError('Unable to load results for this job.')
      } finally {
        setLoadingDoctors(false)
      }
    }
  }

  const progress = job.pages_total > 0
    ? Math.min(100, Math.round((job.pages_crawled / job.pages_total) * 100))
    : job.status === 'done' ? 100 : 0

  return (
    <div className="job-card">
      <div className="job-header">
        <div>
          <div className="job-url">
            {isRunning && <span className="pulsedot" />}
            {job.url}
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: '#aaa', marginTop: 4 }}>
            ID: {job.job_id}
          </div>
        </div>
        <span className={`badge badge-${job.status}`}>{job.status}</span>
      </div>

      <div className="job-stats">
        <div className="stat">
          <span className="stat-val">{job.doctors_found}</span>
          <span className="stat-label">Doctors</span>
        </div>
        <div className="stat">
          <span className="stat-val">{job.pages_crawled}</span>
          <span className="stat-label">Pages</span>
        </div>
        {job.pages_total > 0 && (
          <div className="stat">
            <span className="stat-val">{progress}%</span>
            <span className="stat-label">Progress</span>
          </div>
        )}
      </div>

      <div className="progress-wrap">
        <div
          className={`progress-bar ${job.status}`}
          style={{ width: `${progress}%` }}
        />
      </div>

      {job.error && <div className="error-msg">⚠ {job.error}</div>}

      {job.log && job.log.length > 0 && (
        <>
          <button className="log-toggle" onClick={() => setShowLog(v => !v)}>
            {showLog ? '▲ Hide' : '▼ Show'} log ({job.log.length} entries)
          </button>
          {showLog && (
            <div className="log-box" ref={logRef}>
              {job.log.map((entry, i) => (
                <div
                  key={i}
                  className={`log-entry${entry.msg?.startsWith('ERROR') ? ' err' : ''}`}
                >
                  {entry.msg}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Results table */}
      {job.status === 'done' && job.doctors_found > 0 && (
        <div className="results-section">
          <button className="results-toggle" onClick={handleToggleResults}>
            {showResults ? '▲ Hide' : '▼ Show'} results table ({job.doctors_found})
          </button>
          {resultsError && (
            <div className="error-msg" style={{ marginTop: 4 }}>
              {resultsError}
            </div>
          )}
          {showResults && (
            <div className="results-table-wrap">
              {loadingDoctors ? (
                <div className="results-loading">Loading results…</div>
              ) : doctors.length === 0 ? (
                <div className="results-empty">No doctors stored for this job.</div>
              ) : (
                <>
                  <table className="results-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Title</th>
                        <th>Specialty</th>
                        <th>Email</th>
                        <th>Phone</th>
                        <th>NPI</th>
                        <th>Source</th>
                      </tr>
                    </thead>
                    <tbody>
                      {doctors.slice(0, 50).map(doc => (
                        <tr key={doc.id}>
                          <td>{[doc.first_name, doc.last_name].filter(Boolean).join(' ') || '—'}</td>
                          <td>{doc.title || '—'}</td>
                          <td>{doc.specialty || '—'}</td>
                          <td>{doc.email1 || doc.email2 || '—'}</td>
                          <td>{doc.phone1 || doc.phone2 || '—'}</td>
                          <td>{doc.npi || '—'}</td>
                          <td>
                            {doc.source_url ? (
                              <a href={doc.source_url} target="_blank" rel="noreferrer">
                                Link
                              </a>
                            ) : (
                              '—'
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {doctors.length > 50 && (
                    <div className="results-note">
                      Showing first 50 of {doctors.length} rows. Use CSV download for full data.
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}

      <div className="job-actions">
        {job.csv_ready && (
          <a href={api.downloadUrl(job.job_id)}>
            <button className="btn btn-sm">↓ Download CSV</button>
          </a>
        )}
        {isRunning && (
          <button className="btn btn-ghost btn-sm" onClick={onRefresh}>
            ↻ Refresh
          </button>
        )}
        <button
          className="btn btn-ghost btn-sm"
          style={{ marginLeft: 'auto', color: '#aaa', borderColor: '#ddd' }}
          onClick={() => onDelete(job.job_id)}
        >
          ✕ Delete
        </button>
      </div>
    </div>
  )
}

// ── Main App ───────────────────────────────────────────────────────────────────
export default function App() {
  const [url, setUrl] = useState('')
  const [pageCap, setPageCap] = useState(150)
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const pollRef = useRef(null)

  // Load jobs on mount
  useEffect(() => {
    api.listJobs().then(setJobs).catch(() => {})
  }, [])

  // Poll running jobs
  useEffect(() => {
    const running = jobs.filter(j => j.status === 'running' || j.status === 'pending')
    if (running.length === 0) {
      clearInterval(pollRef.current)
      return
    }

    clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      const updated = await Promise.all(
        running.map(j => api.getJob(j.job_id).catch(() => j))
      )
      setJobs(prev => {
        const map = Object.fromEntries(prev.map(j => [j.job_id, j]))
        updated.forEach(j => { map[j.job_id] = j })
        return Object.values(map).sort((a, b) => 0) // keep order
      })
    }, 2500)

    return () => clearInterval(pollRef.current)
  }, [jobs])

  const handleSubmit = async (e) => {
    e?.preventDefault()
    if (!url.trim()) { setError('Please enter a URL'); return }
    setError('')
    setLoading(true)
    try {
      const job = await api.startScrape(url.trim(), pageCap)
      setJobs(prev => [job, ...prev])
      setUrl('')
    } catch (err) {
      setError('Failed to start job. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (jobId) => {
    await api.deleteJob(jobId).catch(() => {})
    setJobs(prev => prev.filter(j => j.job_id !== jobId))
  }

  const handleRefresh = async (jobId) => {
    const updated = await api.getJob(jobId).catch(() => null)
    if (updated) {
      setJobs(prev => prev.map(j => j.job_id === jobId ? updated : j))
    }
  }

  return (
    <>
      <style>{styles}</style>

      <header className="header">
        <div className="logo">Med<span>Scrape</span></div>
        <div className="header-tag">Hospital Directory Extractor</div>
      </header>

      <div className="container">
        <div className="hero">
          <h1>Extract Doctor<br />Directories <em>Automatically</em></h1>
          <p className="hero-sub">
            Crawl hospital & clinic websites to extract physician names, specialties,
            emails and phone numbers — exported as clean CSV files.
          </p>
        </div>

        {/* Input form */}
        <div className="card">
          <div className="card-title">New Scrape Job</div>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group">
                <label>Hospital URL or Domain</label>
                <input
                  type="text"
                  placeholder="https://hospital.com  or  hospital.com"
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  autoFocus
                />
              </div>
              <div className="form-group narrow">
                <label>Page Cap</label>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={pageCap}
                  onChange={e => setPageCap(Number(e.target.value))}
                />
              </div>
              <button className="btn" type="submit" disabled={loading}>
                {loading ? 'Starting...' : '→ Scrape'}
              </button>
            </div>
            {error && <div className="error-msg">{error}</div>}
          </form>
        </div>

        {/* Jobs list */}
        {jobs.length > 0 ? (
          <>
            <div className="section-label">Active & Past Jobs</div>
            <div className="jobs-grid">
              {jobs.map(job => (
                <JobCard
                  key={job.job_id}
                  job={job}
                  onDelete={handleDelete}
                  onRefresh={() => handleRefresh(job.job_id)}
                />
              ))}
            </div>
          </>
        ) : (
          <div className="empty-state">
            <span className="empty-icon">🏥</span>
            <p>No jobs yet — enter a hospital URL above to begin</p>
          </div>
        )}
      </div>
    </>
  )
}
