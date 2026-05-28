import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateStr: string | null | undefined, opts?: Intl.DateTimeFormatOptions): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleDateString('en-US', opts ?? { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  return new Date(dateStr).toLocaleString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export function formatNumber(value: number | string | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return '—'
  const n = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(n)) return '—'
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

export function formatTonnes(kgCo2e: number | string | null | undefined): string {
  const kg = typeof kgCo2e === 'string' ? parseFloat(kgCo2e) : (kgCo2e ?? 0)
  const t = kg / 1000
  if (t >= 1000) return `${formatNumber(t / 1000, 1)} kt CO₂e`
  if (t >= 1) return `${formatNumber(t, 2)} t CO₂e`
  return `${formatNumber(kg, 1)} kg CO₂e`
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export const SOURCE_LABELS: Record<string, string> = {
  sap: 'SAP Procurement',
  utility: 'Utility',
  travel: 'Travel',
}

export const SCOPE_COLORS: Record<number, string> = {
  1: '#ef4444',
  2: '#f59e0b',
  3: '#3b82f6',
}

export const STATUS_COLORS: Record<string, string> = {
  pending: '#94a3b8',
  flagged: '#f59e0b',
  approved: '#22c55e',
  rejected: '#ef4444',
}

export const SUSPICION_LABELS: Record<string, string> = {
  outlier_3sigma: 'Outlier (>3σ from batch mean)',
  zero_quantity: 'Zero quantity',
  stale_date: 'Activity date >18 months ago',
  future_date: 'Activity date in the future',
  unknown_unit: 'Unknown unit of measure',
  manual_flag: 'Manually flagged by analyst',
}
