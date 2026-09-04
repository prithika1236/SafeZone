export function LoadingState({ label = 'Loading operational data…' }) { return <div className="state-box"><div className="spinner" /><p>{label}</p></div> }
export function EmptyState({ title, message }) { return <div className="state-box empty"><span>○</span><h3>{title}</h3><p>{message}</p></div> }
export function ErrorBanner({ error, onRetry }) { return error ? <div className="error-banner" role="alert"><div><strong>Request failed</strong><p>{error.message}</p></div>{onRetry && <button onClick={onRetry}>Retry</button>}</div> : null }
export function PageHeading({ eyebrow, title, description, actions }) { return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2><p>{description}</p></div>{actions && <div className="heading-actions">{actions}</div>}</div> }
export function StatusPill({ value }) { const key = String(value || '').toLowerCase().replaceAll('_', '-'); return <span className={`status-pill ${key}`}>{String(value || 'UNKNOWN').replaceAll('_', ' ')}</span> }
export function Modal({ title, children, onClose }) { return <div className="modal-backdrop" onMouseDown={onClose}><section className="modal" role="dialog" aria-modal="true" onMouseDown={(e) => e.stopPropagation()}><header><h2>{title}</h2><button onClick={onClose}>×</button></header>{children}</section></div> }
export const formatDate = (value) => value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'
export const shortId = (value) => value ? `${value.slice(0, 8)}…` : '—'
