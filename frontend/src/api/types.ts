export interface Organization {
  id: string
  name: string
  slug: string
  fiscal_year_start_month: number
  default_electricity_grid: string
}

export interface User {
  id: string
  email: string
  username: string
  first_name: string
  last_name: string
  role: 'admin' | 'analyst' | 'auditor'
  organization: Organization | null
}

export type SourceType = 'sap' | 'utility' | 'travel'
export type BatchStatus = 'pending' | 'processing' | 'complete' | 'failed'
export type ReviewStatus = 'pending' | 'flagged' | 'approved' | 'rejected'
export type ParseStatus = 'ok' | 'warning' | 'error' | 'skipped'

export interface IngestionBatch {
  id: string
  source_type: SourceType
  original_filename: string
  file_sha256: string
  file_size_bytes: number
  status: BatchStatus
  row_count_total: number
  row_count_parsed: number
  row_count_failed: number
  row_count_suspicious: number
  parse_errors_summary: string
  uploaded_at: string
  completed_at: string | null
  uploaded_by_name: string | null
}

export interface ParseError {
  field: string
  message: string
}

export interface RawRecord {
  id: string
  row_number: number
  raw_data: Record<string, string>
  parse_status: ParseStatus
  parse_errors: ParseError[]
  created_at: string
}

export interface EmissionFactor {
  id: string
  activity_category: string
  scope: 1 | 2 | 3
  kg_co2e_per_unit: string
  unit: string
  factor_source: string
  valid_from: string
  valid_to: string | null
  notes: string
}

export interface EmissionRecord {
  id: string
  scope: 1 | 2 | 3
  source_type: SourceType
  activity_category: string
  activity_date: string
  vendor: string
  location: string
  department: string
  description?: string
  raw_quantity: string
  raw_unit: string
  raw_currency: string
  normalized_quantity: string
  normalized_unit: string
  quantity_kg_co2e: string
  tonnes_co2e: number
  is_suspicious: boolean
  suspicion_reasons: string[]
  review_status: ReviewStatus
  reviewed_by_name: string | null
  reviewed_at: string | null
  review_notes: string
  is_locked: boolean
  locked_at: string | null
  created_at: string
  updated_at: string
  // Detail only
  batch?: IngestionBatch
  raw_record?: RawRecord
  emission_factor_used?: EmissionFactor
}

export interface AuditLog {
  id: string
  action: string
  performed_by_name: string
  before_state: Record<string, unknown> | null
  after_state: Record<string, unknown> | null
  notes: string
  ip_address: string | null
  timestamp: string
}

export interface DashboardKPIs {
  total_records: number
  pending: number
  flagged: number
  approved: number
  rejected: number
  locked: number
  needs_attention: number
  scope_totals: Array<{
    scope: number
    count: number
    total_kg_co2e: string
  }>
  ingestion_health_30d: {
    total: number
    complete: number
    failed: number
    processing: number
  }
}

export interface ScopeBreakdownPoint {
  month: string
  scope: number
  total_kg_co2e: number
  total_t_co2e: number
}

export interface PaginatedResponse<T> {
  count?: number
  next: string | null
  previous: string | null
  results: T[]
}
