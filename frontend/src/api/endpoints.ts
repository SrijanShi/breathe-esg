import api from './client'
import type {
  AuditLog,
  DashboardKPIs,
  EmissionRecord,
  IngestionBatch,
  PaginatedResponse,
  RawRecord,
  ScopeBreakdownPoint,
  User,
} from './types'

// Auth
export const login = (username: string, password: string) =>
  api.post<{ user: User }>('/auth/login/', { username, password })

export const logout = () => api.post('/auth/logout/')

export const getMe = () => api.get<User>('/auth/me/')

// Dashboard
export const getDashboardKPIs = () => api.get<DashboardKPIs>('/dashboard/kpis/')

export const getScopeBreakdown = (months = 6) =>
  api.get<ScopeBreakdownPoint[]>(`/dashboard/scope-breakdown/?months=${months}`)

// Ingestion
export const getBatches = (params?: Record<string, string>) =>
  api.get<PaginatedResponse<IngestionBatch>>('/ingestion/batches/', { params })

export const getBatch = (id: string) =>
  api.get<IngestionBatch>(`/ingestion/batches/${id}/`)

export const uploadBatch = (formData: FormData) =>
  api.post<IngestionBatch>('/ingestion/batches/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

export const deleteBatch = (id: string) => api.delete(`/ingestion/batches/${id}/`)

export const getBatchRawRecords = (batchId: string, cursor?: string) =>
  api.get<PaginatedResponse<RawRecord>>(
    `/ingestion/batches/${batchId}/raw-records/${cursor ? `?cursor=${cursor}` : ''}`
  )

// Emissions
export interface EmissionsParams {
  scope?: string
  source_type?: string
  review_status?: string
  is_suspicious?: string
  is_locked?: string
  date_from?: string
  date_to?: string
  search?: string
  batch?: string
  cursor?: string
  page_size?: string
}

export const getEmissions = (params?: EmissionsParams) =>
  api.get<PaginatedResponse<EmissionRecord>>('/emissions/', { params })

export const getEmission = (id: string) =>
  api.get<EmissionRecord>(`/emissions/${id}/`)

export const approveEmission = (id: string, notes?: string) =>
  api.post<EmissionRecord>(`/emissions/${id}/approve/`, { notes })

export const rejectEmission = (id: string, notes: string) =>
  api.post<EmissionRecord>(`/emissions/${id}/reject/`, { notes })

export const flagEmission = (id: string, reason?: string) =>
  api.post<EmissionRecord>(`/emissions/${id}/flag/`, { reason })

export const lockEmission = (id: string) =>
  api.post<EmissionRecord>(`/emissions/${id}/lock/`)

export const bulkApprove = (ids: string[], notes?: string) =>
  api.post('/emissions/bulk-approve/', { ids, notes })

export const bulkReject = (ids: string[], notes: string) =>
  api.post('/emissions/bulk-reject/', { ids, notes })

export const getRecordAudit = (id: string) =>
  api.get<AuditLog[]>(`/emissions/${id}/audit/`)

// Audit
export const getAuditLog = (params?: Record<string, string>) =>
  api.get<PaginatedResponse<AuditLog>>('/audit/', { params })
