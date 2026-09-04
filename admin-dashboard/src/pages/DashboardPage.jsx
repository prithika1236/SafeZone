import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/apiClient.js'
import { ErrorBanner, LoadingState, PageHeading, StatusPill, formatDate } from '../components/UI.jsx'

export default function DashboardPage() {
  const [data, setData] = useState(null); const [error, setError] = useState(null)
  const load = useCallback(async () => {
    setError(null)
    const results = await Promise.allSettled([api.crimes({ limit: 5, offset: 0 }), api.activePrps(), api.assignments({ limit: 200, offset: 0 })])
    const failed = results.find((item) => item.status === 'rejected')
    if (failed) setError(failed.reason)
    setData({ crimes: results[0].status === 'fulfilled' ? results[0].value : { total: 0, items: [] }, prps: results[1].status === 'fulfilled' ? results[1].value : [], assignments: results[2].status === 'fulfilled' ? results[2].value : { total: 0, items: [] } })
  }, [])
  useEffect(() => { load() }, [load])
  if (!data) return <LoadingState />
  const openAssignments = data.assignments.items.filter((item) => !['COMPLETED', 'CANCELLED'].includes(item.status))
  const assignedUnits = new Set(openAssignments.map((item) => item.patrol_unit_id)).size
  return <><PageHeading eyebrow="Operational overview" title="Command snapshot" description="Live information available from the current SafeZone backend." actions={<button className="secondary-button" onClick={load}>Refresh data</button>} /><ErrorBanner error={error} onRetry={load} />
    <section className="metric-grid"><Metric label="Crime incidents" value={data.crimes.total} note="Relevant records" tone="red" icon="◇" /><Metric label="Active PRPs" value={data.prps.length} note="Approved deployments" tone="blue" icon="△" /><Metric label="Assigned patrols" value={assignedUnits} note={`${openAssignments.length} open assignments`} tone="amber" icon="⇄" /><Metric label="Available patrols" value="—" note="Inventory API not available" tone="slate" icon="○" /></section>
    <div className="dashboard-grid"><section className="panel"><div className="panel-heading"><div><p className="eyebrow">LATEST ACTIVITY</p><h3>Recent crime incidents</h3></div><Link to="/crimes">Manage crimes →</Link></div>{data.crimes.items.length ? <div className="activity-list">{data.crimes.items.map((crime) => <div key={crime.id} className="activity-row"><span className={`severity-dot severity-${crime.severity}`}>{crime.severity}</span><div><strong>{crime.crime_type}</strong><small>{crime.area || crime.ward || 'Area not recorded'} · {formatDate(crime.occurred_at)}</small></div><StatusPill value={crime.status} /></div>)}</div> : <p className="inline-empty">No crime incidents have been recorded.</p>}</section>
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">DEPLOYMENT</p><h3>Active assignments</h3></div><Link to="/assignments">View all →</Link></div>{openAssignments.length ? <div className="activity-list">{openAssignments.slice(0, 5).map((item) => <div key={item.id} className="activity-row"><span className="assignment-icon">⇄</span><div><strong>Patrol {item.patrol_unit_id.slice(0, 8)}</strong><small>Shift ends {formatDate(item.shift_end)}</small></div><StatusPill value={item.status} /></div>)}</div> : <p className="inline-empty">No active patrol assignments.</p>}</section>
    </div><div className="info-note"><strong>SOS summary unavailable</strong><span>The backend does not expose an ADMIN SOS listing/count endpoint yet, so this dashboard does not fabricate one.</span></div></>
}
function Metric({ label, value, note, tone, icon }) { return <article className={`metric-card ${tone}`}><div className="metric-icon">{icon}</div><div><span>{label}</span><strong>{value}</strong><small>{note}</small></div></article> }
