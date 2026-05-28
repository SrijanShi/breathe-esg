import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
  type RowSelectionState,
} from '@tanstack/react-table'
import {
  getEmissions,
  approveEmission,
  rejectEmission,
  flagEmission,
  lockEmission,
  bulkApprove,
  bulkReject,
} from '@/api/endpoints'
import type { EmissionRecord } from '@/api/types'
import { formatDate, formatTonnes, SOURCE_LABELS, SUSPICION_LABELS } from '@/lib/utils'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { ScopePill } from '@/components/shared/ScopePill'
import { RecordDrawer } from '@/components/review/RecordDrawer'
import { useAuth } from '@/hooks/useAuth'
import {
  CheckCircle2, XCircle, AlertTriangle, Lock, Filter,
  ChevronLeft, ChevronRight, Search, Loader2, Flag, X
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface Filters {
  scope: string
  source_type: string
  review_status: string
  is_suspicious: string
  date_from: string
  date_to: string
  search: string
}

const DEFAULT_FILTERS: Filters = {
  scope: '',
  source_type: '',
  review_status: '',
  is_suspicious: '',
  date_from: '',
  date_to: '',
  search: '',
}

function SuspicionTooltip({ reasons }: { reasons: string[] }) {
  return (
    <div className="group relative inline-flex">
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-amber-100 border border-amber-200 text-amber-700 text-[10px] font-medium cursor-help">
        <AlertTriangle className="w-3 h-3" />
        {reasons.length}
      </span>
      <div className="absolute bottom-full left-0 mb-1.5 hidden group-hover:block z-20 w-56 bg-slate-900 text-white text-xs rounded-lg p-2.5 shadow-xl">
        <p className="font-semibold mb-1 text-slate-300">Suspicion flags:</p>
        <ul className="space-y-0.5">
          {reasons.map(r => (
            <li key={r} className="text-slate-200">• {SUSPICION_LABELS[r] ?? r}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function ApproveRejectModal({
  mode,
  count,
  onConfirm,
  onClose,
}: {
  mode: 'approve' | 'reject'
  count: number
  onConfirm: (notes: string) => void
  onClose: () => void
}) {
  const [notes, setNotes] = useState('')
  const isReject = mode === 'reject'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900">
              {isReject ? 'Reject' : 'Approve'} {count} record{count !== 1 ? 's' : ''}
            </h3>
            <p className="text-sm text-slate-500 mt-0.5">
              {isReject
                ? 'Provide a reason for rejection (required)'
                : 'Optionally add a note for the audit trail'}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            <X className="w-5 h-5" />
          </button>
        </div>
        <textarea
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder={isReject ? 'e.g. Duplicate entry from prior batch, unit mismatch...' : 'Optional note...'}
          rows={3}
          className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 resize-none"
        />
        <div className="flex gap-3 mt-4">
          <button onClick={onClose} className="flex-1 py-2 rounded-lg border border-slate-200 text-sm font-medium text-slate-600 hover:bg-slate-50">
            Cancel
          </button>
          <button
            onClick={() => onConfirm(notes)}
            disabled={isReject && !notes.trim()}
            className={cn(
              'flex-1 py-2 rounded-lg text-sm font-semibold text-white transition-colors disabled:opacity-50',
              isReject ? 'bg-red-600 hover:bg-red-500' : 'bg-emerald-600 hover:bg-emerald-500'
            )}
          >
            {isReject ? 'Reject' : 'Approve'}
          </button>
        </div>
      </div>
    </div>
  )
}

const columnHelper = createColumnHelper<EmissionRecord>()

export function ReviewQueuePage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const isReadOnly = user?.role === 'auditor'

  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [cursor, setCursor] = useState<string | undefined>()
  const [cursorStack, setCursorStack] = useState<string[]>([])
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const [selectedRecord, setSelectedRecord] = useState<EmissionRecord | null>(null)
  const [modal, setModal] = useState<{ mode: 'approve' | 'reject'; ids: string[] } | null>(null)

  const queryParams = {
    ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== '')),
    cursor,
    page_size: '50',
  }

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['emissions', queryParams],
    queryFn: () => getEmissions(queryParams).then(r => r.data),
    placeholderData: prev => prev,
  })

  const patchCache = (ids: string[], patch: Partial<EmissionRecord>) => {
    queryClient.setQueriesData<{ results: EmissionRecord[]; next: string | null; previous: string | null }>(
      { queryKey: ['emissions'] },
      old => old ? { ...old, results: old.results.map(r => ids.includes(r.id) ? { ...r, ...patch } : r) } : old
    )
    queryClient.invalidateQueries({ queryKey: ['dashboard-kpis'] })
    setRowSelection({})
  }

  const approveMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) => approveEmission(id, notes),
    onMutate: ({ id }) => patchCache([id], { review_status: 'approved' }),
    onError: () => queryClient.invalidateQueries({ queryKey: ['emissions'] }),
  })
  const rejectMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes: string }) => rejectEmission(id, notes),
    onMutate: ({ id }) => patchCache([id], { review_status: 'rejected' }),
    onError: () => queryClient.invalidateQueries({ queryKey: ['emissions'] }),
  })
  const flagMutation = useMutation({
    mutationFn: (id: string) => flagEmission(id),
    onMutate: (id) => {
      const record = queryClient.getQueriesData<{ results: EmissionRecord[] }>({ queryKey: ['emissions'] })
        .flatMap(([, d]) => d?.results ?? [])
        .find(r => r.id === id)
      patchCache([id], { is_suspicious: !record?.is_suspicious })
    },
    onError: () => queryClient.invalidateQueries({ queryKey: ['emissions'] }),
  })
  const lockMutation = useMutation({
    mutationFn: (id: string) => lockEmission(id),
    onMutate: (id) => patchCache([id], { is_locked: true }),
    onError: () => queryClient.invalidateQueries({ queryKey: ['emissions'] }),
  })
  const bulkApproveMutation = useMutation({
    mutationFn: ({ ids, notes }: { ids: string[]; notes?: string }) => bulkApprove(ids, notes),
    onMutate: ({ ids }) => patchCache(ids, { review_status: 'approved' }),
    onError: () => queryClient.invalidateQueries({ queryKey: ['emissions'] }),
  })
  const bulkRejectMutation = useMutation({
    mutationFn: ({ ids, notes }: { ids: string[]; notes: string }) => bulkReject(ids, notes),
    onMutate: ({ ids }) => patchCache(ids, { review_status: 'rejected' }),
    onError: () => queryClient.invalidateQueries({ queryKey: ['emissions'] }),
  })

  const selectedIds = Object.keys(rowSelection).filter(id => rowSelection[id])

  const columns = [
    columnHelper.display({
      id: 'select',
      header: ({ table }) => (
        <input
          type="checkbox"
          className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
          checked={table.getIsAllRowsSelected()}
          onChange={table.getToggleAllRowsSelectedHandler()}
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          className="rounded border-slate-300 text-emerald-600 focus:ring-emerald-500"
          checked={row.getIsSelected()}
          onChange={row.getToggleSelectedHandler()}
          onClick={e => e.stopPropagation()}
        />
      ),
      size: 40,
    }),
    columnHelper.accessor('scope', {
      header: 'Scope',
      cell: info => <ScopePill scope={info.getValue()} />,
      size: 80,
    }),
    columnHelper.accessor('source_type', {
      header: 'Source',
      cell: info => <span className="text-xs text-slate-600">{SOURCE_LABELS[info.getValue()]}</span>,
      size: 110,
    }),
    columnHelper.accessor('activity_category', {
      header: 'Category',
      cell: info => (
        <span className="text-xs font-mono text-slate-700">
          {info.getValue().replace(/_/g, ' ')}
        </span>
      ),
      size: 160,
    }),
    columnHelper.accessor('activity_date', {
      header: 'Date',
      cell: info => <span className="text-xs text-slate-600">{formatDate(info.getValue())}</span>,
      size: 100,
    }),
    columnHelper.accessor('vendor', {
      header: 'Vendor',
      cell: info => (
        <span className="text-xs text-slate-700 truncate block max-w-[140px]" title={info.getValue()}>
          {info.getValue() || '—'}
        </span>
      ),
      size: 140,
    }),
    columnHelper.accessor('quantity_kg_co2e', {
      header: 'CO₂e',
      cell: info => (
        <span className="text-xs font-medium text-slate-800">{formatTonnes(info.getValue())}</span>
      ),
      size: 100,
    }),
    columnHelper.display({
      id: 'flags',
      header: '',
      cell: ({ row }) => {
        const r = row.original
        return r.is_suspicious ? <SuspicionTooltip reasons={r.suspicion_reasons} /> : null
      },
      size: 40,
    }),
    columnHelper.accessor('review_status', {
      header: 'Status',
      cell: info => <StatusBadge status={info.getValue()} />,
      size: 90,
    }),
    columnHelper.display({
      id: 'actions',
      header: '',
      cell: ({ row }) => {
        const r = row.original
        if (isReadOnly || r.is_locked) return r.is_locked ? <span title="Locked"><Lock className="w-3.5 h-3.5 text-slate-400" /></span> : null
        return (
          <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
            {r.review_status !== 'approved' && (
              <button
                onClick={() => setModal({ mode: 'approve', ids: [r.id] })}
                className="p-1 rounded hover:bg-emerald-50 text-emerald-600 hover:text-emerald-700"
                title="Approve"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
              </button>
            )}
            {r.review_status !== 'rejected' && (
              <button
                onClick={() => setModal({ mode: 'reject', ids: [r.id] })}
                className="p-1 rounded hover:bg-red-50 text-red-500 hover:text-red-600"
                title="Reject"
              >
                <XCircle className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              onClick={() => flagMutation.mutate(r.id)}
              className={cn(
                'p-1 rounded',
                r.is_suspicious
                  ? 'text-amber-500 hover:bg-amber-50'
                  : 'text-slate-300 hover:bg-slate-100 hover:text-amber-500'
              )}
              title={r.is_suspicious ? 'Clear flag' : 'Flag as suspicious'}
            >
              <Flag className="w-3.5 h-3.5" />
            </button>
            {user?.role === 'admin' && r.review_status === 'approved' && !r.is_locked && (
              <button
                onClick={() => lockMutation.mutate(r.id)}
                className="p-1 rounded text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                title="Lock for audit"
              >
                <Lock className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        )
      },
      size: 120,
    }),
  ]

  const table = useReactTable({
    data: data?.results ?? [],
    columns,
    state: { rowSelection },
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getRowId: row => row.id,
    enableRowSelection: true,
  })

  const setFilter = (key: keyof Filters, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }))
    setCursor(undefined)
    setCursorStack([])
  }

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

  const handleModalConfirm = (notes: string) => {
    if (!modal) return
    if (modal.mode === 'approve') {
      if (modal.ids.length === 1) {
        approveMutation.mutate({ id: modal.ids[0], notes })
      } else {
        bulkApproveMutation.mutate({ ids: modal.ids, notes })
      }
    } else {
      if (modal.ids.length === 1) {
        rejectMutation.mutate({ id: modal.ids[0], notes })
      } else {
        bulkRejectMutation.mutate({ ids: modal.ids, notes })
      }
    }
    setModal(null)
  }

  const activeFilterCount = Object.values(filters).filter(v => v !== '').length

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="px-8 pt-8 pb-4 border-b border-slate-200 bg-white">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Review Queue</h1>
            <p className="text-slate-500 text-sm mt-0.5">
              {data?.results.length ?? 0} records shown
              {isFetching && <Loader2 className="inline w-3 h-3 animate-spin ml-2 text-slate-400" />}
            </p>
          </div>
          {!isReadOnly && selectedIds.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-600 font-medium">{selectedIds.length} selected</span>
              <button
                onClick={() => setModal({ mode: 'approve', ids: selectedIds })}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-500"
              >
                <CheckCircle2 className="w-4 h-4" /> Approve
              </button>
              <button
                onClick={() => setModal({ mode: 'reject', ids: selectedIds })}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-500"
              >
                <XCircle className="w-4 h-4" /> Reject
              </button>
            </div>
          )}
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Filter className="w-3.5 h-3.5" />
            <span>Filter</span>
            {activeFilterCount > 0 && (
              <span className="bg-emerald-100 text-emerald-700 rounded-full px-1.5 py-0.5 font-semibold">{activeFilterCount}</span>
            )}
          </div>

          <select
            value={filters.scope}
            onChange={e => setFilter('scope', e.target.value)}
            className="h-8 px-2 pr-6 text-xs rounded-lg border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
          >
            <option value="">All scopes</option>
            <option value="1">Scope 1</option>
            <option value="2">Scope 2</option>
            <option value="3">Scope 3</option>
          </select>

          <select
            value={filters.source_type}
            onChange={e => setFilter('source_type', e.target.value)}
            className="h-8 px-2 pr-6 text-xs rounded-lg border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
          >
            <option value="">All sources</option>
            <option value="sap">SAP</option>
            <option value="utility">Utility</option>
            <option value="travel">Travel</option>
          </select>

          <select
            value={filters.review_status}
            onChange={e => setFilter('review_status', e.target.value)}
            className="h-8 px-2 pr-6 text-xs rounded-lg border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="flagged">Flagged</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>

          <select
            value={filters.is_suspicious}
            onChange={e => setFilter('is_suspicious', e.target.value)}
            className="h-8 px-2 pr-6 text-xs rounded-lg border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
          >
            <option value="">All</option>
            <option value="true">⚠ Suspicious only</option>
            <option value="false">Clean only</option>
          </select>

          <input
            type="date"
            value={filters.date_from}
            onChange={e => setFilter('date_from', e.target.value)}
            className="h-8 px-2 text-xs rounded-lg border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
            placeholder="From"
          />
          <input
            type="date"
            value={filters.date_to}
            onChange={e => setFilter('date_to', e.target.value)}
            className="h-8 px-2 text-xs rounded-lg border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/30"
          />

          <div className="flex items-center gap-1.5 h-8 px-2 rounded-lg border border-slate-200 bg-white">
            <Search className="w-3.5 h-3.5 text-slate-400" />
            <input
              type="text"
              value={filters.search}
              onChange={e => setFilter('search', e.target.value)}
              placeholder="Search vendor, location..."
              className="text-xs text-slate-700 bg-transparent focus:outline-none w-44 placeholder-slate-400"
            />
          </div>

          {activeFilterCount > 0 && (
            <button
              onClick={() => { setFilters(DEFAULT_FILTERS); setCursor(undefined); setCursorStack([]) }}
              className="h-8 px-2 rounded-lg text-xs text-slate-500 hover:text-slate-700 hover:bg-slate-100 flex items-center gap-1"
            >
              <X className="w-3.5 h-3.5" /> Clear
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto bg-white">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-6 h-6 animate-spin text-emerald-600" />
          </div>
        ) : data?.results.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-400">
            <CheckCircle2 className="w-10 h-10 mb-3 text-slate-200" />
            <p className="text-sm font-medium text-slate-600">No records match your filters</p>
            <p className="text-xs mt-1">Try adjusting the filter options above</p>
          </div>
        ) : (
          <table className="w-full text-sm border-collapse">
            <thead className="sticky top-0 bg-slate-50 border-b border-slate-200 z-10">
              {table.getHeaderGroups().map(hg => (
                <tr key={hg.id}>
                  {hg.headers.map(header => (
                    <th
                      key={header.id}
                      className="px-3 py-2.5 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap"
                      style={{ width: header.getSize() }}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-slate-100">
              {table.getRowModel().rows.map(row => {
                const r = row.original
                return (
                  <tr
                    key={row.id}
                    onClick={() => setSelectedRecord(r)}
                    className={cn(
                      'cursor-pointer hover:bg-slate-50/80 transition-colors',
                      row.getIsSelected() && 'bg-emerald-50',
                      r.is_suspicious && !row.getIsSelected() && 'bg-amber-50/60'
                    )}
                  >
                    {row.getVisibleCells().map(cell => (
                      <td key={cell.id} className="px-3 py-2.5" style={{ width: cell.column.getSize() }}>
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-6 py-3 border-t border-slate-200 bg-white">
        <span className="text-xs text-slate-500">
          Showing {data?.results.length ?? 0} records
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrev}
            disabled={cursorStack.length === 0}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="w-3.5 h-3.5" /> Previous
          </button>
          <button
            onClick={handleNext}
            disabled={!data?.next}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Next <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Record drawer */}
      {selectedRecord && (
        <RecordDrawer
          record={selectedRecord}
          onClose={() => setSelectedRecord(null)}
          onApprove={(id, notes) => { approveMutation.mutate({ id, notes }); setSelectedRecord(null) }}
          onReject={(id, notes) => { rejectMutation.mutate({ id, notes }); setSelectedRecord(null) }}
          isReadOnly={isReadOnly}
        />
      )}

      {/* Approve/Reject modal */}
      {modal && (
        <ApproveRejectModal
          mode={modal.mode}
          count={modal.ids.length}
          onConfirm={handleModalConfirm}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  )
}
