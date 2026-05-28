import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useDropzone } from 'react-dropzone'
import { getBatches, uploadBatch, getBatchRawRecords } from '@/api/endpoints'
import { formatDateTime, formatBytes } from '@/lib/utils'
import { StatusBadge } from '@/components/shared/StatusBadge'
import type { SourceType, IngestionBatch } from '@/api/types'
import {
  Upload, CheckCircle2, AlertTriangle, XCircle, FileText,
  ChevronDown, ChevronUp, Loader2, CloudUpload, Info,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const SOURCE_TABS: { id: SourceType; label: string; description: string; columns: string[] }[] = [
  {
    id: 'sap',
    label: 'SAP Procurement',
    description: 'SAP ME2N / MIRO flat-file CSV export. Handles German field names (BUKRS, BLDAT, MATNR, MENGE, MEINS, WERKS, LIFNR) and DD.MM.YYYY dates.',
    columns: ['BUKRS', 'BLDAT', 'BUDAT', 'MATNR', 'MATKL', 'TXZ01', 'MENGE', 'MEINS', 'NETWR', 'WAERS', 'WERKS', 'LIFNR', 'NAME1', 'KOSTL'],
  },
  {
    id: 'utility',
    label: 'Utility Data',
    description: 'Green Button Alliance portal CSV export (daily or monthly granularity). Handles kWh, MWh, and daily interval data.',
    columns: ['TYPE', 'DATE', 'START TIME', 'END TIME', 'CONSUMPTION', 'UNITS', 'NOTES'],
  },
  {
    id: 'travel',
    label: 'Corporate Travel',
    description: 'SAP Concur standard expense report CSV. Covers flights, hotels, and rail. Distance calculated via haversine if not provided.',
    columns: ['Report ID', 'Transaction Date', 'Expense Type', 'Merchant Name', 'Amount', 'Currency', 'Origin City', 'Destination City', 'Distance', 'Class', 'Nights', 'Employee ID'],
  },
]

function Dropzone({ onFile, disabled }: { onFile: (file: File) => void; disabled?: boolean }) {
  const [dragOver, setDragOver] = useState(false)
  const onDrop = useCallback((files: File[]) => {
    if (files[0]) onFile(files[0])
  }, [onFile])

  const { getRootProps, getInputProps } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'text/plain': ['.txt', '.csv'] },
    maxFiles: 1,
    disabled,
    onDragEnter: () => setDragOver(true),
    onDragLeave: () => setDragOver(false),
    onDropAccepted: () => setDragOver(false),
    onDropRejected: () => setDragOver(false),
  })

  return (
    <div
      {...getRootProps()}
      className={cn(
        'border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all',
        dragOver ? 'border-emerald-400 bg-emerald-50' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50',
        disabled && 'opacity-50 cursor-not-allowed'
      )}
    >
      <input {...getInputProps()} />
      <CloudUpload className={cn('w-8 h-8 mx-auto mb-3', dragOver ? 'text-emerald-500' : 'text-slate-300')} />
      <p className="text-sm font-medium text-slate-700">Drop CSV file here, or click to select</p>
      <p className="text-xs text-slate-400 mt-1">CSV only · max 20MB</p>
    </div>
  )
}

function BatchCard({ batch }: { batch: IngestionBatch }) {
  const [expanded, setExpanded] = useState(false)
  const { data: rawRecords } = useQuery({
    queryKey: ['raw-records', batch.id],
    queryFn: () => getBatchRawRecords(batch.id).then((r) => r.data),
    enabled: expanded,
  })

  return (
    <div className="border border-slate-200 rounded-xl overflow-hidden bg-white">
      <div className="flex items-center gap-3 p-4">
        <FileText className="w-4 h-4 text-slate-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-800 truncate">{batch.original_filename}</p>
          <p className="text-xs text-slate-400 mt-0.5">
            {formatDateTime(batch.uploaded_at)} · {formatBytes(batch.file_size_bytes)}
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <StatusBadge status={batch.status} />
          {batch.status === 'complete' && (
            <span className="text-xs text-slate-500">
              {batch.row_count_parsed}✓
              {batch.row_count_failed > 0 && <span className="text-red-500 ml-1">{batch.row_count_failed}✗</span>}
              {batch.row_count_suspicious > 0 && <span className="text-amber-500 ml-1">{batch.row_count_suspicious}⚠</span>}
            </span>
          )}
          {batch.row_count_failed > 0 || batch.parse_errors_summary ? (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-slate-400 hover:text-slate-600 ml-1"
            >
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          ) : null}
        </div>
      </div>
      {expanded && batch.parse_errors_summary && (
        <div className="border-t border-slate-100 p-4 bg-amber-50">
          <p className="text-xs font-semibold text-amber-700 mb-2">Parse errors:</p>
          <pre className="text-xs text-amber-800 whitespace-pre-wrap font-mono leading-relaxed">
            {batch.parse_errors_summary}
          </pre>
        </div>
      )}
      {expanded && rawRecords && rawRecords.results.length > 0 && (
        <div className="border-t border-slate-100">
          <table className="w-full text-xs">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-slate-500">Row</th>
                <th className="px-4 py-2 text-left font-medium text-slate-500">Status</th>
                <th className="px-4 py-2 text-left font-medium text-slate-500">Errors</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rawRecords.results.filter(r => r.parse_status !== 'ok').slice(0, 10).map((row) => (
                <tr key={row.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2 text-slate-600">{row.row_number}</td>
                  <td className="px-4 py-2"><StatusBadge status={row.parse_status} /></td>
                  <td className="px-4 py-2 text-red-600">
                    {row.parse_errors.map(e => `${e.field}: ${e.message}`).join(' · ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function IngestionPage() {
  const [activeTab, setActiveTab] = useState<SourceType>('sap')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploadError, setUploadError] = useState('')
  const queryClient = useQueryClient()

  const tab = SOURCE_TABS.find(t => t.id === activeTab)!

  const { data: batches, isLoading } = useQuery({
    queryKey: ['batches', activeTab],
    queryFn: () => getBatches({ source_type: activeTab, page_size: '10' }).then(r => r.data),
  })

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!selectedFile) throw new Error('No file selected')
      const fd = new FormData()
      fd.append('file', selectedFile)
      fd.append('source_type', activeTab)
      return uploadBatch(fd).then(r => r.data)
    },
    onSuccess: () => {
      setSelectedFile(null)
      setUploadError('')
      queryClient.invalidateQueries({ queryKey: ['batches'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-kpis'] })
      queryClient.invalidateQueries({ queryKey: ['emissions'] })
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail ?? 'Upload failed'
      const existingId = err?.response?.data?.existing_batch_id
      setUploadError(existingId ? `${detail} (Batch ID: ${existingId})` : detail)
    },
  })

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Data Ingestion</h1>
        <p className="text-slate-500 text-sm mt-1">Upload emissions data files for parsing and normalization</p>
      </div>

      {/* Source tabs */}
      <div className="flex gap-1 mb-6 bg-slate-100 rounded-xl p-1">
        {SOURCE_TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => { setActiveTab(t.id); setSelectedFile(null); setUploadError('') }}
            className={cn(
              'flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-colors',
              activeTab === t.id
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-500 hover:text-slate-700'
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Upload card */}
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm mb-6">
        {/* Description */}
        <div className="flex items-start gap-3 mb-4 p-3 rounded-lg bg-blue-50 border border-blue-100">
          <Info className="w-4 h-4 text-blue-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-blue-800 font-medium">{tab.label} format</p>
            <p className="text-xs text-blue-700 mt-1">{tab.description}</p>
            <div className="flex flex-wrap gap-1 mt-2">
              {tab.columns.map(c => (
                <span key={c} className="text-[10px] font-mono bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">{c}</span>
              ))}
            </div>
          </div>
        </div>

        <Dropzone
          onFile={setSelectedFile}
          disabled={uploadMutation.isPending}
        />

        {selectedFile && (
          <div className="mt-3 flex items-center justify-between p-3 rounded-lg bg-slate-50 border border-slate-200">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-slate-500" />
              <span className="text-sm font-medium text-slate-700">{selectedFile.name}</span>
              <span className="text-xs text-slate-400">{formatBytes(selectedFile.size)}</span>
            </div>
            <button onClick={() => setSelectedFile(null)} className="text-slate-400 hover:text-red-500">
              <XCircle className="w-4 h-4" />
            </button>
          </div>
        )}

        {uploadError && (
          <div className="mt-3 flex items-start gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            {uploadError}
          </div>
        )}

        {uploadMutation.isSuccess && (
          <div className="mt-3 flex items-center gap-2 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm">
            <CheckCircle2 className="w-4 h-4" />
            File processed successfully
          </div>
        )}

        <button
          onClick={() => uploadMutation.mutate()}
          disabled={!selectedFile || uploadMutation.isPending}
          className="mt-4 w-full py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-sm transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {uploadMutation.isPending ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Processing...</>
          ) : (
            <><Upload className="w-4 h-4" /> Upload & Process</>
          )}
        </button>
      </div>

      {/* Recent batches */}
      <div>
        <h2 className="text-sm font-semibold text-slate-700 mb-3">
          Recent {tab.label} batches
        </h2>
        {isLoading ? (
          <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-slate-400" /></div>
        ) : batches?.results.length === 0 ? (
          <div className="text-center py-8 text-sm text-slate-400 border border-dashed border-slate-200 rounded-xl">
            No {tab.label.toLowerCase()} batches yet
          </div>
        ) : (
          <div className="space-y-3">
            {batches?.results.map(batch => (
              <BatchCard key={batch.id} batch={batch} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
