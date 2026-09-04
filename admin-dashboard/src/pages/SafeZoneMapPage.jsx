import { useCallback, useEffect, useState } from 'react'
import OperationsMap from '../maps/OperationsMap.jsx'
import { api } from '../services/apiClient.js'
import { ErrorBanner, LoadingState, PageHeading } from '../components/UI.jsx'

export default function SafeZoneMapPage() {
  const [data, setData] = useState(null); const [error, setError] = useState(null); const [visible, setVisible] = useState({ crimes: true, prps: true, proposed: true })
  const load = useCallback(async () => {
    setError(null)
    const results = await Promise.allSettled([api.crimes({ limit: 100, offset: 0 }), api.activePrps(), api.assignments({ limit: 200, offset: 0 })])
    const failed = results.find((r) => r.status === 'rejected'); if (failed) setError(failed.reason)
    let proposed = []; try { proposed = JSON.parse(sessionStorage.getItem('safezone.last.proposed_prps') || '[]') } catch { /* ignore invalid local display cache */ }
    setData({ crimes: results[0].status === 'fulfilled' ? results[0].value.items : [], prps: results[1].status === 'fulfilled' ? results[1].value : [], assignments: results[2].status === 'fulfilled' ? results[2].value.items : [], proposed })
  }, [])
  useEffect(() => { load() }, [load])
  return <><PageHeading eyebrow="Authorized operational view" title="SafeZone map" description="Crime evidence and strategic patrol deployment layers on OpenStreetMap." actions={<button className="secondary-button" onClick={load}>Refresh layers</button>} /><ErrorBanner error={error} onRetry={load} />{!data ? <LoadingState label="Loading map layers…" /> : <section className="map-panel"><div className="layer-controls"><strong>Map layers</strong><label><input type="checkbox" checked={visible.crimes} onChange={() => setVisible({ ...visible, crimes: !visible.crimes })} /><span className="legend-dot crime" />Crime incidents ({data.crimes.length})</label><label><input type="checkbox" checked={visible.prps} onChange={() => setVisible({ ...visible, prps: !visible.prps })} /><span className="legend-dot prp" />Active PRPs ({data.prps.length})</label><label><input type="checkbox" checked={visible.proposed} onChange={() => setVisible({ ...visible, proposed: !visible.proposed })} /><span className="legend-dot proposed" />Last proposed PRPs ({data.proposed.length})</label><label><span className="legend-dot deployed" />Assigned PRP coverage</label><hr /><small>Crime marker size/color represents recorded severity evidence, not a newly calculated risk score. Exact operational layers are ADMIN-only.</small></div><OperationsMap {...data} proposedPrps={data.proposed} visible={visible} /></section>}</>
}
