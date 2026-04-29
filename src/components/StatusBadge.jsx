/**
 * 상태 뱃지 컴포넌트
 */
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react'

const VARIANTS = {
  idle: { bg: 'bg-slate-700/50', text: 'text-slate-400', icon: null },
  loading: { bg: 'bg-blue-900/30', text: 'text-blue-400', icon: Loader2 },
  success: { bg: 'bg-emerald-900/30', text: 'text-emerald-400', icon: CheckCircle2 },
  error: { bg: 'bg-red-900/30', text: 'text-red-400', icon: AlertCircle },
}

export default function StatusBadge({ status = 'idle', label }) {
  const v = VARIANTS[status] || VARIANTS.idle
  const Icon = v.icon

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${v.bg} ${v.text}`}>
      {Icon && <Icon size={12} className={status === 'loading' ? 'animate-spin' : ''} />}
      {label}
    </span>
  )
}
