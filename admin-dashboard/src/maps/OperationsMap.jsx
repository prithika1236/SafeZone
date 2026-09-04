import { Circle, CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import { useEffect } from 'react'
import L from 'leaflet'
import { formatDate } from '../components/UI.jsx'

function FitData({ points }) {
  const map = useMap()
  useEffect(() => {
    if (!points.length) return
    if (points.length === 1) map.setView(points[0], 14)
    else map.fitBounds(L.latLngBounds(points), { padding: [35, 35], maxZoom: 15 })
  }, [map, points])
  return null
}
const crimeColor = (severity) => severity >= 5 ? '#b42318' : severity >= 4 ? '#e04f3f' : severity >= 3 ? '#f59e0b' : '#f7c948'
export default function OperationsMap({ crimes, prps, proposedPrps, assignments, visible }) {
  const points = [
    ...(visible.crimes ? crimes.map((c) => [c.latitude, c.longitude]) : []),
    ...(visible.prps ? prps.map((p) => [p.location.latitude, p.location.longitude]) : []),
    ...(visible.proposed ? proposedPrps.map((p) => [p.location.latitude, p.location.longitude]) : []),
  ]
  const assignedPrpIds = new Set(assignments.filter((a) => !['COMPLETED','CANCELLED'].includes(a.status)).map((a) => a.prp_location_id))
  return <MapContainer center={[12.9716, 77.5946]} zoom={12} className="operations-map" scrollWheelZoom>
    <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
    <FitData points={points} />
    {visible.crimes && crimes.map((crime) => <CircleMarker key={crime.id} center={[crime.latitude, crime.longitude]} radius={5 + crime.severity * 1.4} pathOptions={{ color: '#fff', weight: 1.5, fillColor: crimeColor(crime.severity), fillOpacity: .78 }}><Popup><strong>{crime.crime_type}</strong><br />Severity {crime.severity}<br />{crime.area || crime.ward || 'Area not recorded'}<br /><small>{formatDate(crime.occurred_at)}</small></Popup></CircleMarker>)}
    {visible.prps && prps.map((prp) => <Circle key={prp.id} center={[prp.location.latitude, prp.location.longitude]} radius={prp.coverage_radius_meters} pathOptions={{ color: assignedPrpIds.has(prp.id) ? '#0f766e' : '#2563eb', weight: 2, fillOpacity: .08 }}><Popup><strong>Active PRP</strong><br />Risk {Number(prp.risk_score).toFixed(2)} · Covered {Number(prp.covered_risk).toFixed(2)}<br />Radius {Math.round(prp.coverage_radius_meters)} m</Popup></Circle>)}
    {visible.proposed && proposedPrps.map((prp) => <CircleMarker key={prp.id || prp.candidate_id} center={[prp.location.latitude, prp.location.longitude]} radius={9} pathOptions={{ color: '#7c3aed', fillColor: '#a78bfa', fillOpacity: .8 }}><Popup><strong>Proposed PRP</strong><br />{prp.candidate_id}</Popup></CircleMarker>)}
  </MapContainer>
}
