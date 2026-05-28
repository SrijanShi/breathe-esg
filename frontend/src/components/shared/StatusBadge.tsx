import { cn } from '@/lib/utils'

interface Props {
  status: string
  size?: 'sm' | 'md'
}

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  pending: { label: 'Pending', className: 'bg-slate-100 text-slate-600 border-slate-200' },
  flagged: { label: 'Flagged', className: 'bg-amber-50 text-amber-700 border-amber-200' },
  approved: { label: 'Approved', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  rejected: { label: 'Rejected', className: 'bg-red-50 text-red-700 border-red-200' },
  complete: { label: 'Complete', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  failed: { label: 'Failed', className: 'bg-red-50 text-red-700 border-red-200' },
  processing: { label: 'Processing', className: 'bg-blue-50 text-blue-700 border-blue-200' },
  ok: { label: 'OK', className: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  warning: { label: 'Warning', className: 'bg-amber-50 text-amber-700 border-amber-200' },
  error: { label: 'Error', className: 'bg-red-50 text-red-700 border-red-200' },
}

export function StatusBadge({ status, size = 'sm' }: Props) {
  const config = STATUS_CONFIG[status] ?? { label: status, className: 'bg-slate-100 text-slate-500 border-slate-200' }
  return (
    <span className={cn(
      'inline-flex items-center rounded-full border font-medium',
      size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm',
      config.className
    )}>
      {config.label}
    </span>
  )
}
