/**
 * 모듈: 이미지 업로드
 * 면별로 이미지를 드래그&드롭 또는 클릭 업로드
 * 다른 모듈과의 의존성: 없음
 */
import { useState, useRef } from 'react'
import { Upload, Plus, Trash2 } from 'lucide-react'
import { FACES, FACE_LABELS } from '../../utils/constants'
import ImagePreview from '../../components/ImagePreview'

export default function UploadStep({ uploadedFiles, onFilesChange }) {
  const [dragOver, setDragOver] = useState(null) // 어떤 면에 드래그 중인지

  const handleFiles = (face, fileList) => {
    const files = Array.from(fileList).filter(f => f.type.startsWith('image/'))
    if (files.length === 0) return
    const existing = uploadedFiles[face] || []
    onFilesChange(face, [...existing, ...files])
  }

  const handleRemove = (face, index) => {
    const files = [...(uploadedFiles[face] || [])]
    files.splice(index, 1)
    onFilesChange(face, files)
  }

  const handleDrop = (face, e) => {
    e.preventDefault()
    setDragOver(null)
    handleFiles(face, e.dataTransfer.files)
  }

  const totalFiles = Object.values(uploadedFiles).reduce((sum, arr) => sum + (arr?.length || 0), 0)

  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-lg font-medium text-slate-200 mb-1">이미지 업로드</h2>
        <p className="text-sm text-slate-400">
          건물의 각 면(전/후/좌/우/상)별로 촬영한 이미지를 업로드하세요.
          한 면에 여러 장을 올리면 파노라마 합성 대상이 됩니다.
        </p>
        {totalFiles > 0 && (
          <p className="text-xs text-slate-500 mt-1">총 {totalFiles}개 파일 업로드됨</p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {FACES.map(face => {
          const files = uploadedFiles[face] || []
          const isDragTarget = dragOver === face

          return (
            <div key={face} className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-slate-300">{FACE_LABELS[face]}</span>
                {files.length > 0 && (
                  <span className="text-xs text-slate-500">{files.length}장</span>
                )}
              </div>

              {/* 드롭 영역 */}
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(face) }}
                onDragLeave={() => setDragOver(null)}
                onDrop={(e) => handleDrop(face, e)}
                className={`
                  relative border-2 border-dashed rounded-xl p-4 transition-all min-h-[120px]
                  flex flex-col items-center justify-center gap-2 cursor-pointer
                  ${isDragTarget
                    ? 'border-blue-500 bg-blue-500/10'
                    : 'border-slate-700 hover:border-slate-500 bg-slate-800/30'
                  }
                `}
                onClick={() => document.getElementById(`file-${face}`).click()}
              >
                <input
                  id={`file-${face}`}
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={(e) => handleFiles(face, e.target.files)}
                />
                {files.length === 0 ? (
                  <>
                    <Upload size={24} className="text-slate-500" />
                    <span className="text-xs text-slate-500">클릭 또는 드래그</span>
                  </>
                ) : (
                  <div className="w-full grid grid-cols-2 gap-2">
                    {files.map((file, idx) => (
                      <ImagePreview
                        key={idx}
                        src={URL.createObjectURL(file)}
                        label={file.name}
                        onRemove={() => handleRemove(face, idx)}
                        className="aspect-video"
                      />
                    ))}
                    <div
                      className="aspect-video border-2 border-dashed border-slate-700 rounded-lg flex items-center justify-center hover:border-slate-500 transition-colors"
                      onClick={(e) => { e.stopPropagation(); document.getElementById(`file-${face}`).click() }}
                    >
                      <Plus size={20} className="text-slate-500" />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
