import { cn } from '@/lib/utils'

interface Props {
  scope: 1 | 2 | 3
  size?: 'sm' | 'md'
}

const SCOPE_CONFIG = {
  1: { label: 'Scope 1', className: 'bg-red-100 text-red-700 border-red-200' },
  2: { label: 'Scope 2', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  3: { label: 'Scope 3', className: 'bg-blue-100 text-blue-700 border-blue-200' },
}

export function ScopePill({ scope, size = 'sm' }: Props) {
  const config = SCOPE_CONFIG[scope] ?? { label: `Scope ${scope}`, className: 'bg-slate-100 text-slate-600 border-slate-200' }
  return (
    <span className={cn(
      'inline-flex items-center rounded-full border font-semibold',
      size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-sm',
      config.className
    )}>
      {config.label}
    </span>
  )
}
