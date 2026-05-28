import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAuditLog } from '@/api/endpoints'
import { formatDateTime } from '@/lib/utils'
import {
  ScrollText, Loader2, ChevronLeft, ChevronRight,
  Download, Pencil, CheckCircle2, XCircle, Flag, Lock, LockOpen,
} from 'lucide-react'

const ACTION_META: Record<string, { icon: React.ElementType; iconClass: string }> = {
  created:        { icon: Download,      iconClass: 'text-slate-400' },
  edited:         { icon: Pencil,        iconClass: 'text-blue-400' },
  approved:       { icon: CheckCircle2,  iconClass: 'text-emerald-500' },
  batch_approved: { icon: CheckCircle2,  iconClass: 'text-emerald-500' },
  rejected:       { icon: XCircle,       iconClass: 'text-red-500' },
  batch_rejected: { icon: XCircle,       iconClass: 'text-red-500' },
  flagged:        { icon: Flag,          iconClass: 'text-amber-500' },
  unflagged:      { icon: Flag,          iconClass: 'text-slate-400' },
  locked:         { icon: Lock,          iconClass: 'text-slate-500' },
  unlocked:       { icon: LockOpen,      iconClass: 'text-slate-400' },
}

const ACTION_COLORS: Record<string, string> = {
  approved: 'bg-emerald-50 border-emerald-100 text-emerald-800',
  batch_approved: 'bg-emerald-50 border-emerald-100 text-emerald-800',
  rejected: 'bg-red-50 border-red-100 text-red-800',
  batch_rejected: 'bg-red-50 border-red-100 text-red-800',
  flagged: 'bg-amber-50 border-amber-100 text-amber-800',
  locked: 'bg-slate-100 border-slate-200 text-slate-700',
}

export function AuditPage() {
  const [action, setAction] = useState('analyst')
  const [cursor, setCursor] = useState<string | undefined>()
  const [cursorStack, setCursorStack] = useState<string[]>([])

  const buildParams = () => {
    const p: Record<string, string> = {}
    if (action === 'created') { p.action = 'created' }
    else if (action === 'all') { p.include_created = '1' }
    else if (action && action !== 'analyst') { p.action = action }
    if (cursor) p.cursor = cursor
    return p
  }

  const { data, isLoading } = useQuery({
    queryKey: ['audit-log', action, cursor],
    queryFn: () => getAuditLog(buildParams()).then(r => r.data),
  })

  const handleNext = () => {
    if (data?.next) {
      const url = new URL(data.next)
      const nextCursor = url.searchParams.get('cursor') ?? undefined
      if (cursor) setCursorStack(prev => [...prev, cursor])
      setCursor(nextCursor)
    }
  }

  const handlePrev = () => {
    const prev = cursorStack[cursorStack.length - 1]
    setCursorStack(s => s.slice(0, -1))
    setCursor(prev)
  }

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Audit Trail</h1>
        <p className="text-slate-500 text-sm mt-1">
          Complete immutable history of all record changes in your organization
        </p>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3 mb-6">
        <select
          value={action}
          onChange={e => { setAction(e.target.value); setCursor(undefined); setCursorStack([]) }}
          className="h-9 px-3 pr-8 text-sm rounded-lg border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
        >
          <option value="analyst">Analyst actions</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="batch_approved">Bulk approved</option>
          <option value="batch_rejected">Bulk rejected</option>
          <option value="flagged">Flagged</option>
          <option value="edited">Edited</option>
          <option value="locked">Locked</option>
          <option value="created">Ingestion (created)</option>
          <option value="all">All (including ingestion)</option>
        </select>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-emerald-600" />
        </div>
      ) : data?.results.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-400">
          <ScrollText className="w-10 h-10 mb-3 text-slate-200" />
          <p className="text-sm font-medium text-slate-600">No entries for this filter</p>
          <p className="text-xs mt-1">Try "All (including ingestion)" to see creation events</p>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm divide-y divide-slate-100">
          {data?.results.map((log) => {
            const colorClass = ACTION_COLORS[log.action] ?? 'bg-slate-50 border-slate-100 text-slate-700'
            const meta = ACTION_META[log.action]
            const ActionIcon = meta?.icon ?? Download
            return (
              <div key={log.id} className="flex items-start gap-4 px-5 py-4">
                <ActionIcon className={`w-4 h-4 shrink-0 mt-0.5 ${meta?.iconClass ?? 'text-slate-300'}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${colorClass} capitalize`}>
                      {log.action.replace(/_/g, ' ')}
                    </span>
                    <span className="text-xs text-slate-500">by</span>
                    <span className="text-xs font-medium text-slate-700">{log.performed_by_name}</span>
                    <span className="text-xs text-slate-400">{formatDateTime(log.timestamp)}</span>
                    {log.ip_address && (
                      <span className="text-[10px] font-mono text-slate-300">{log.ip_address}</span>
                    )}
                  </div>

                  {log.notes && (
                    <p className="text-xs text-slate-600 mt-1 italic">"{log.notes}"</p>
                  )}

                  {log.before_state && log.after_state && (
                    <div className="mt-1.5 text-[10px] font-mono bg-slate-50 rounded p-2 text-slate-600 flex flex-wrap gap-x-4 gap-y-0.5">
                      {Object.keys({ ...log.before_state, ...log.after_state }).map(k => {
                        const before = log.before_state?.[k]
                        const after = log.after_state?.[k]
                        if (before === after) return null
                        return (
                          <span key={k}>
                            <span className="text-slate-400">{k}: </span>
                            <span className="text-red-500 line-through">{String(before ?? '—')}</span>
                            {' → '}
                            <span className="text-emerald-600">{String(after ?? '—')}</span>
                          </span>
                        )
                      })}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {(data?.next || cursorStack.length > 0) && (
        <div className="flex items-center justify-end gap-2 mt-4">
          <button
            onClick={handlePrev}
            disabled={cursorStack.length === 0}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 border border-slate-200 hover:bg-slate-50 disabled:opacity-40"
          >
            <ChevronLeft className="w-3.5 h-3.5" /> Previous
          </button>
          <button
            onClick={handleNext}
            disabled={!data?.next}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 border border-slate-200 hover:bg-slate-50 disabled:opacity-40"
          >
            Next <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  )
}
