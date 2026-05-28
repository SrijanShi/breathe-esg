import { useQuery } from '@tanstack/react-query'
import { getDashboardKPIs, getScopeBreakdown, getBatches } from '@/api/endpoints'
import { formatTonnes, formatDateTime, SOURCE_LABELS, SCOPE_COLORS } from '@/lib/utils'
import { StatusBadge } from '@/components/shared/StatusBadge'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { AlertTriangle, CheckCircle2, Upload, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'

function KpiCard({
  label,
  value,
  icon: Icon,
  iconColor,
  sub,
  to,
}: {
  label: string
  value: number | string
  icon: React.ElementType
  iconColor: string
  sub?: string
  to?: string
}) {
  const content = (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:shadow-md transition-shadow group">
      <div className="flex items-center gap-1.5 mb-3">
        <Icon className={`w-3.5 h-3.5 ${iconColor}`} />
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{label}</p>
      </div>
      <p className="text-2xl font-bold text-slate-900 tabular-nums">{value}</p>
      {sub && <p className="mt-1.5 text-xs text-slate-400">{sub}</p>}
    </div>
  )
  if (to) return <Link to={to}>{content}</Link>
  return content
}

function ScopeChart({ data }: { data: any[] }) {
  const monthMap: Record<string, Record<string, number>> = {}
  for (const d of data) {
    if (!monthMap[d.month]) monthMap[d.month] = {}
    monthMap[d.month][`scope${d.scope}`] = d.total_t_co2e
  }
  const chartData = Object.entries(monthMap).map(([month, vals]) => ({ month, ...vals }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData} margin={{ top: 0, right: 0, left: -10, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#94a3b8' }} />
        <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} unit=" t" />
        <Tooltip
          contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
          formatter={(v) => [`${Number(v ?? 0).toFixed(2)} t CO₂e`, '']}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="scope1" name="Scope 1" fill={SCOPE_COLORS[1]} radius={[3, 3, 0, 0]} />
        <Bar dataKey="scope2" name="Scope 2" fill={SCOPE_COLORS[2]} radius={[3, 3, 0, 0]} />
        <Bar dataKey="scope3" name="Scope 3" fill={SCOPE_COLORS[3]} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function DashboardPage() {
  const { data: kpis, isLoading: kpisLoading } = useQuery({
    queryKey: ['dashboard-kpis'],
    queryFn: () => getDashboardKPIs().then((r) => r.data),
    refetchInterval: 30_000,
  })

  const { data: breakdown } = useQuery({
    queryKey: ['scope-breakdown'],
    queryFn: () => getScopeBreakdown(6).then((r) => r.data),
  })

  const { data: batches } = useQuery({
    queryKey: ['batches-recent'],
    queryFn: () => getBatches({ page_size: '5' }).then((r) => r.data),
  })

  if (kpisLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-emerald-600" />
      </div>
    )
  }

  const totalTonnes = kpis?.scope_totals.reduce(
    (acc, s) => acc + (parseFloat(s.total_kg_co2e) / 1000), 0
  ) ?? 0

  return (
    <div className="p-8 max-w-7xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-slate-500 text-sm mt-1">Emissions data overview for your organization</p>
      </div>

      {/* Attention banner */}
      {kpis && kpis.needs_attention > 0 && (
        <div className="mb-6 flex items-center gap-3 p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800">
          <AlertTriangle className="w-5 h-5 shrink-0 text-amber-500" />
          <div>
            <span className="font-semibold">{kpis.needs_attention} records</span> need analyst review.{' '}
            <Link to="/review" className="underline underline-offset-2 font-medium hover:text-amber-900">
              Go to Review Queue →
            </Link>
          </div>
        </div>
      )}

      {/* KPI strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard
          label="Needs attention"
          value={kpis?.needs_attention ?? 0}
          icon={AlertTriangle}
          iconColor="text-amber-500"
          sub={`${kpis?.pending ?? 0} pending · ${kpis?.flagged ?? 0} flagged`}
          to="/review?review_status=pending"
        />
        <KpiCard
          label="Total emissions"
          value={formatTonnes(totalTonnes * 1000)}
          icon={CheckCircle2}
          iconColor="text-emerald-600"
          sub={`${kpis?.total_records ?? 0} records total`}
        />
        <KpiCard
          label="Approved"
          value={kpis?.approved ?? 0}
          icon={CheckCircle2}
          iconColor="text-blue-500"
          sub={`${kpis?.locked ?? 0} locked for audit`}
        />
        <KpiCard
          label="Ingestion failures"
          value={kpis?.ingestion_health_30d.failed ?? 0}
          icon={Upload}
          iconColor="text-slate-400"
          sub="Last 30 days"
          to="/ingestion"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Scope chart */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Emissions by Scope</h2>
              <p className="text-xs text-slate-400 mt-0.5">Last 6 months · tCO₂e</p>
            </div>
          </div>
          {breakdown && breakdown.length > 0 ? (
            <ScopeChart data={breakdown} />
          ) : (
            <div className="h-52 flex items-center justify-center text-slate-400 text-sm">
              No data yet — upload your first file to get started
            </div>
          )}
        </div>

        {/* Scope summary */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-900 mb-4">Scope totals (all time)</h2>
          <div className="space-y-3">
            {[1, 2, 3].map((scope) => {
              const found = kpis?.scope_totals.find((s) => s.scope === scope)
              const tonnes = (parseFloat(found?.total_kg_co2e ?? '0')) / 1000
              return (
                <div key={scope} className="flex items-center gap-3">
                  <div
                    className="w-3 h-3 rounded-full shrink-0"
                    style={{ backgroundColor: SCOPE_COLORS[scope] }}
                  />
                  <div className="flex-1">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium text-slate-700">Scope {scope}</span>
                      <span className="text-slate-600 font-medium">{formatTonnes(tonnes * 1000)}</span>
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">{found?.count ?? 0} records</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Recent batches */}
      <div className="mt-6 bg-white rounded-xl border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-900">Recent Ingestion Batches</h2>
          <Link to="/ingestion" className="text-xs text-emerald-600 font-medium hover:underline">
            View all →
          </Link>
        </div>
        <div className="divide-y divide-slate-100">
          {batches?.results.length === 0 && (
            <p className="text-sm text-slate-400 text-center py-8">No batches yet</p>
          )}
          {batches?.results.map((batch) => (
            <div key={batch.id} className="flex items-center gap-4 px-6 py-3.5">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-800 truncate">{batch.original_filename}</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  {SOURCE_LABELS[batch.source_type]} · {formatDateTime(batch.uploaded_at)}
                  {batch.uploaded_by_name ? ` · ${batch.uploaded_by_name}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <StatusBadge status={batch.status} />
                {batch.status === 'complete' && (
                  <span className="text-xs text-slate-400">
                    {batch.row_count_parsed} parsed
                    {batch.row_count_suspicious > 0 && (
                      <span className="text-amber-500 ml-1">· {batch.row_count_suspicious} ⚠</span>
                    )}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
