import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getEmission, getRecordAudit } from '@/api/endpoints'
import type { EmissionRecord } from '@/api/types'
import { formatDate, formatDateTime, formatNumber, formatTonnes, SOURCE_LABELS, SUSPICION_LABELS } from '@/lib/utils'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { ScopePill } from '@/components/shared/ScopePill'
import { cn } from '@/lib/utils'
import {
  X, AlertTriangle, CheckCircle2, XCircle, Lock, ChevronRight,
  FileText, BarChart3, Clock, Database, Download, Pencil, Flag, LockOpen,
} from 'lucide-react'

interface Props {
  record: EmissionRecord
  onClose: () => void
  onApprove: (id: string, notes?: string) => void
  onReject: (id: string, notes: string) => void
  isReadOnly?: boolean
}

export function RecordDrawer({ record, onClose, onApprove, onReject, isReadOnly }: Props) {
  const [tab, setTab] = useState<'overview' | 'provenance' | 'audit'>('overview')
  const [rejectNotes, setRejectNotes] = useState('')
  const [showReject, setShowReject] = useState(false)

  const { data: detail } = useQuery({
    queryKey: ['emission-detail', record.id],
    queryFn: () => getEmission(record.id).then(r => r.data),
    initialData: record,
  })

  const { data: auditLogs } = useQuery({
    queryKey: ['record-audit', record.id],
    queryFn: () => getRecordAudit(record.id).then(r => r.data),
    enabled: tab === 'audit',
  })

  const canAct = !isReadOnly && !detail.is_locked

  const AUDIT_META: Record<string, { icon: React.ElementType; cls: string }> = {
    created:        { icon: Download,     cls: 'text-slate-400' },
    edited:         { icon: Pencil,       cls: 'text-blue-400' },
    approved:       { icon: CheckCircle2, cls: 'text-emerald-500' },
    batch_approved: { icon: CheckCircle2, cls: 'text-emerald-500' },
    rejected:       { icon: XCircle,      cls: 'text-red-500' },
    batch_rejected: { icon: XCircle,      cls: 'text-red-500' },
    flagged:        { icon: Flag,         cls: 'text-amber-500' },
    unflagged:      { icon: Flag,         cls: 'text-slate-300' },
    locked:         { icon: Lock,         cls: 'text-slate-500' },
    unlocked:       { icon: LockOpen,     cls: 'text-slate-400' },
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      {/* Backdrop */}
      <div className="flex-1 bg-black/30 backdrop-blur-sm" onClick={onClose} />

      {/* Drawer */}
      <div className="w-full max-w-lg bg-white shadow-2xl flex flex-col h-full overflow-hidden">
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-slate-200">
          <div className="flex items-center gap-2.5">
            <ScopePill scope={detail.scope} size="md" />
            <div>
              <p className="text-sm font-semibold text-slate-900 capitalize">
                {detail.activity_category.replace(/_/g, ' ')}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                {SOURCE_LABELS[detail.source_type]} · {formatDate(detail.activity_date)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={detail.review_status} size="md" />
            {detail.is_locked && <Lock className="w-4 h-4 text-slate-400" />}
            <button onClick={onClose} className="ml-1 text-slate-400 hover:text-slate-600 transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Suspicious banner */}
        {detail.is_suspicious && (
          <div className="flex items-start gap-2 px-5 py-3 bg-amber-50 border-b border-amber-100">
            <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-amber-800">Flagged as suspicious</p>
              <p className="text-xs text-amber-700 mt-0.5">
                {detail.suspicion_reasons.map(r => SUSPICION_LABELS[r] ?? r).join(' · ')}
              </p>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex border-b border-slate-200 px-5">
          {([
            ['overview', BarChart3, 'Overview'],
            ['provenance', Database, 'Provenance'],
            ['audit', Clock, 'Audit Trail'],
          ] as const).map(([id, Icon, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={cn(
                'flex items-center gap-1.5 py-3 px-1 mr-5 text-xs font-medium border-b-2 transition-colors',
                tab === id
                  ? 'border-emerald-600 text-emerald-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {tab === 'overview' && (
            <div className="space-y-4">
              {/* CO2e card */}
              <div className="bg-emerald-50 rounded-xl p-4 border border-emerald-100">
                <p className="text-xs text-emerald-600 font-medium mb-1">Total Emissions</p>
                <p className="text-2xl font-bold text-emerald-800">{formatTonnes(detail.quantity_kg_co2e)}</p>
                <p className="text-xs text-emerald-600 mt-0.5">
                  {formatNumber(detail.quantity_kg_co2e, 2)} kg CO₂e
                </p>
              </div>

              {/* Normalization chain */}
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <p className="text-xs font-semibold text-slate-700 mb-3 flex items-center gap-1.5">
                  <BarChart3 className="w-3.5 h-3.5 text-slate-400" />
                  Normalization chain
                </p>
                <div className="flex items-center gap-2 text-xs">
                  <div className="flex-1 min-w-0 bg-slate-50 rounded-lg p-2.5 text-center">
                    <p className="font-medium text-slate-800">{formatNumber(detail.raw_quantity)}</p>
                    <p className="text-slate-500 mt-0.5">{detail.raw_unit}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">Raw</p>
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                  <div className="flex-1 min-w-0 bg-slate-50 rounded-lg p-2.5 text-center">
                    <p className="font-medium text-slate-800">{formatNumber(detail.normalized_quantity)}</p>
                    <p className="text-slate-500 mt-0.5">{detail.normalized_unit}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">Normalized</p>
                  </div>
                  <ChevronRight className="w-3.5 h-3.5 text-slate-300 shrink-0" />
                  <div className="flex-1 min-w-0 bg-emerald-50 rounded-lg p-2.5 text-center border border-emerald-100">
                    <p className="font-semibold text-emerald-800">{formatNumber(detail.quantity_kg_co2e)}</p>
                    <p className="text-emerald-600 mt-0.5">kg CO₂e</p>
                    <p className="text-[10px] text-emerald-500 mt-0.5">Result</p>
                  </div>
                </div>
                {detail.emission_factor_used && (
                  <p className="text-[10px] text-slate-400 mt-2.5 text-center">
                    Factor: {detail.emission_factor_used.kg_co2e_per_unit} kgCO₂e/{detail.emission_factor_used.unit}
                    {' '}({detail.emission_factor_used.factor_source.toUpperCase()} {detail.emission_factor_used.valid_from?.slice(0, 4)})
                  </p>
                )}
              </div>

              {/* Activity details */}
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <p className="text-xs font-semibold text-slate-700 mb-3">Activity details</p>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-xs">
                  {[
                    ['Vendor', detail.vendor],
                    ['Location', detail.location],
                    ['Department', detail.department],
                    ['Currency', detail.raw_currency],
                  ].map(([label, value]) => value ? (
                    <div key={label as string}>
                      <dt className="text-slate-400">{label}</dt>
                      <dd className="font-medium text-slate-800 mt-0.5 truncate">{value}</dd>
                    </div>
                  ) : null)}
                  {detail.description && (
                    <div className="col-span-2">
                      <dt className="text-slate-400">Description</dt>
                      <dd className="font-medium text-slate-800 mt-0.5 text-xs leading-relaxed">{detail.description}</dd>
                    </div>
                  )}
                </dl>
              </div>

              {/* Review history */}
              {detail.reviewed_by_name && (
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <p className="text-xs font-semibold text-slate-700 mb-2">Review</p>
                  <p className="text-xs text-slate-600">
                    <span className="capitalize font-medium">{detail.review_status}</span> by{' '}
                    <span className="font-medium">{detail.reviewed_by_name}</span>
                    {detail.reviewed_at && ` on ${formatDateTime(detail.reviewed_at)}`}
                  </p>
                  {detail.review_notes && (
                    <p className="text-xs text-slate-500 mt-1.5 italic">"{detail.review_notes}"</p>
                  )}
                </div>
              )}
            </div>
          )}

          {tab === 'provenance' && (
            <div className="space-y-4">
              {detail.batch && (
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <p className="text-xs font-semibold text-slate-700 mb-3 flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-slate-400" />
                    Source batch
                  </p>
                  <dl className="space-y-2.5 text-xs">
                    <div>
                      <dt className="text-slate-400">Filename</dt>
                      <dd className="font-medium text-slate-800 mt-0.5">{detail.batch.original_filename}</dd>
                    </div>
                    <div>
                      <dt className="text-slate-400">Uploaded</dt>
                      <dd className="font-medium text-slate-800 mt-0.5">{formatDateTime(detail.batch.uploaded_at)}</dd>
                    </div>
                    {detail.batch.uploaded_by_name && (
                      <div>
                        <dt className="text-slate-400">By</dt>
                        <dd className="font-medium text-slate-800 mt-0.5">{detail.batch.uploaded_by_name}</dd>
                      </div>
                    )}
                    <div>
                      <dt className="text-slate-400">SHA-256</dt>
                      <dd className="font-mono text-[10px] text-slate-600 mt-0.5 break-all bg-slate-50 rounded p-1.5">
                        {detail.batch.file_sha256}
                      </dd>
                    </div>
                  </dl>
                </div>
              )}

              {detail.raw_record && (
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <p className="text-xs font-semibold text-slate-700 mb-3 flex items-center gap-1.5">
                    <Database className="w-3.5 h-3.5 text-slate-400" />
                    Raw source row (row {detail.raw_record.row_number})
                  </p>
                  <div className="bg-slate-50 rounded-lg p-3 text-[10px] font-mono text-slate-700 space-y-1 max-h-48 overflow-y-auto">
                    {Object.entries(detail.raw_record.raw_data).map(([k, v]) => (
                      <div key={k} className="flex gap-2">
                        <span className="text-slate-400 shrink-0">{k}:</span>
                        <span className="break-all">{String(v)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {tab === 'audit' && (
            <div>
              {!auditLogs ? (
                <div className="flex justify-center py-8">
                  <div className="w-4 h-4 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : auditLogs.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-8">No audit history</p>
              ) : (
                <div className="relative">
                  <div className="absolute left-3.5 top-0 bottom-0 w-px bg-slate-200" />
                  <div className="space-y-4">
                    {auditLogs.map((log) => (
                      <div key={log.id} className="flex gap-3 relative">
                        <div className="w-7 h-7 rounded-full bg-white border-2 border-slate-200 flex items-center justify-center shrink-0 z-10">
                          {(() => { const m = AUDIT_META[log.action]; const I = m?.icon ?? Download; return <I className={`w-3.5 h-3.5 ${m?.cls ?? 'text-slate-300'}`} /> })()}
                        </div>
                        <div className="flex-1 pb-1">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold text-slate-800 capitalize">
                              {log.action.replace(/_/g, ' ')}
                            </span>
                            <span className="text-[10px] text-slate-400">{formatDateTime(log.timestamp)}</span>
                          </div>
                          <p className="text-xs text-slate-500 mt-0.5">{log.performed_by_name}</p>
                          {log.notes && (
                            <p className="text-xs text-slate-600 mt-1 italic">"{log.notes}"</p>
                          )}
                          {log.before_state && log.after_state && (
                            <div className="mt-1.5 text-[10px] font-mono bg-slate-50 rounded p-2 text-slate-600 space-y-0.5">
                              {Object.keys({ ...log.before_state, ...log.after_state }).map(k => {
                                const before = log.before_state?.[k]
                                const after = log.after_state?.[k]
                                if (before === after) return null
                                return (
                                  <div key={k}>
                                    <span className="text-slate-400">{k}: </span>
                                    <span className="text-red-500 line-through">{String(before ?? '—')}</span>
                                    {' → '}
                                    <span className="text-emerald-600">{String(after ?? '—')}</span>
                                  </div>
                                )
                              })}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Action bar */}
        {canAct && tab === 'overview' && (
          <div className="p-4 border-t border-slate-200 bg-white">
            {!showReject ? (
              <div className="flex gap-2">
                {detail.review_status !== 'approved' && (
                  <button
                    onClick={() => onApprove(detail.id)}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-500 transition-colors"
                  >
                    <CheckCircle2 className="w-4 h-4" /> Approve
                  </button>
                )}
                {detail.review_status !== 'rejected' && (
                  <button
                    onClick={() => setShowReject(true)}
                    className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg border border-red-200 text-red-600 text-sm font-medium hover:bg-red-50 transition-colors"
                  >
                    <XCircle className="w-4 h-4" /> Reject
                  </button>
                )}
              </div>
            ) : (
              <div>
                <textarea
                  value={rejectNotes}
                  onChange={e => setRejectNotes(e.target.value)}
                  placeholder="Reason for rejection (required)..."
                  rows={2}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-xs text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-red-300 resize-none"
                  autoFocus
                />
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => setShowReject(false)}
                    className="flex-1 py-2 rounded-lg text-xs text-slate-600 border border-slate-200 hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => { onReject(detail.id, rejectNotes); setShowReject(false) }}
                    disabled={!rejectNotes.trim()}
                    className="flex-1 py-2 rounded-lg bg-red-600 text-white text-xs font-medium hover:bg-red-500 disabled:opacity-50"
                  >
                    Confirm Reject
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
