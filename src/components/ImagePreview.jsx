/**
 * 재사용 가능한 이미지 프리뷰 컴포넌트
 * 업로드 이미지, 처리 결과 등을 표시
 */
import { X, ZoomIn } from 'lucide-react'
import { useState } from 'react'

export default function ImagePreview({ src, label, onRemove, className = '' }) {
  const [zoomed, setZoomed] = useState(false)

  if (!src) return null

  return (
    <>
      <div className={`relative group rounded-lg overflow-hidden border border-slate-700/50 bg-slate-800/50 ${className}`}>
        <img
          src={src}
          alt={label || '이미지'}
          className="w-full h-full object-cover"
          loading="lazy"
        />
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all flex items-center justify-center opacity-0 group-hover:opacity-100">
          <button
            onClick={() => setZoomed(true)}
            className="p-2 bg-black/50 rounded-full text-white hover:bg-black/70"
          >
            <ZoomIn size={18} />
          </button>
        </div>
        {label && (
          <div className="absolute bottom-0 left-0 right-0 px-2 py-1 bg-black/60 text-xs text-slate-300 truncate">
            {label}
          </div>
        )}
        {onRemove && (
          <button
            onClick={onRemove}
            className="absolute top-1 right-1 p-1 bg-black/60 rounded-full text-slate-400 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <X size={14} />
          </button>
        )}
      </div>

      {/* 확대 모달 */}
      {zoomed && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-8 cursor-zoom-out"
          onClick={() => setZoomed(false)}
        >
          <img src={src} alt={label} className="max-w-full max-h-full object-contain rounded-lg" />
        </div>
      )}
    </>
  )
}
