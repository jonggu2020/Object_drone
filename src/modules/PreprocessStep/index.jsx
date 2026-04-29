/**
 * 모듈: 전처리 (메디안 스무딩 + 엣지 검출 + 배경 분리)
 * 면별 N장 모두 전처리 실행 및 이미지별 결과 표시
 * 다른 모듈과의 의존성: 없음 (props로 데이터 수신)
 */
import { useState } from 'react'
import { Play, RotateCcw } from 'lucide-react'
import { FACES, FACE_LABELS } from '../../utils/constants'
import { preprocessAPI } from '../../utils/api'
import ImagePreview from '../../components/ImagePreview'
import StatusBadge from '../../components/StatusBadge'

const RESULT_LABELS = {
  smoothed: '스무딩',
  edges: '엣지 검출',
  lines_vis: '직선 검출',
  quad_vis: '꼭짓점 검출',
  mask: '마스크',
  warped: '정면 보정',
  separated: '배경 분리',
}

export default function PreprocessStep({ uploadedFiles, results, onResult }) {
  const [processing, setProcessing] = useState({})
  const [ksize, setKsize] = useState(5)

  // 개별 이미지 1장 처리
  const processOne = async (face, file, index) => {
    const key = `${face}-${index}`
    setProcessing(prev => ({ ...prev, [key]: true }))
    try {
      const res = await preprocessAPI.upload(file, face, ksize)
      // results[face]를 배열로 관리
      onResult(face, prev => {
        const arr = Array.isArray(prev) ? [...prev] : []
        arr[index] = res.data
        return arr
      })
    } catch (err) {
      onResult(face, prev => {
        const arr = Array.isArray(prev) ? [...prev] : []
        arr[index] = { error: err.message }
        return arr
      })
    } finally {
      setProcessing(prev => ({ ...prev, [key]: false }))
    }
  }

  // 한 면의 모든 이미지 순차 처리
  const processFace = async (face) => {
    const files = uploadedFiles[face] || []
    for (let i = 0; i < files.length; i++) {
      await processOne(face, files[i], i)
    }
  }

  // 전체 면 실행
  const processAll = async () => {
    for (const face of FACES) {
      if (uploadedFiles[face]?.length > 0) {
        await processFace(face)
      }
    }
  }

  const facesWithFiles = FACES.filter(f => uploadedFiles[f]?.length > 0)
  const anyProcessing = Object.values(processing).some(Boolean)

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-medium text-slate-200 mb-1">이미지 전처리</h2>
          <p className="text-sm text-slate-400">
            메디안 스무딩 → 엣지 검출 → 배경 분리 파이프라인 실행
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-400">
            <span>커널</span>
            <select
              value={ksize}
              onChange={e => setKsize(Number(e.target.value))}
              className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-slate-300"
            >
              <option value={3}>3</option>
              <option value={5}>5</option>
              <option value={7}>7</option>
            </select>
          </label>
          <button
            onClick={processAll}
            disabled={facesWithFiles.length === 0 || anyProcessing}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg text-sm font-medium transition-colors"
          >
            <Play size={14} />
            전체 실행
          </button>
        </div>
      </div>

      {facesWithFiles.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          먼저 이미지를 업로드하세요
        </div>
      ) : (
        <div className="space-y-6">
          {facesWithFiles.map(face => {
            const files = uploadedFiles[face] || []
            const faceResults = Array.isArray(results[face]) ? results[face] : []
            const doneCount = faceResults.filter(r => r && !r.error).length

            return (
              <div key={face} className="bg-slate-800/40 rounded-xl p-4 border border-slate-700/50">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-300">{FACE_LABELS[face]}</span>
                    <span className="text-xs text-slate-500">{doneCount}/{files.length}장 완료</span>
                    {doneCount === files.length && files.length > 0 && (
                      <StatusBadge status="success" label="전체 완료" />
                    )}
                  </div>
                  <button
                    onClick={() => processFace(face)}
                    disabled={anyProcessing}
                    className="flex items-center gap-1 px-3 py-1.5 text-xs bg-slate-700 hover:bg-slate-600 disabled:opacity-50 rounded-lg transition-colors"
                  >
                    <Play size={12} />
                    {files.length}장 실행
                  </button>
                </div>

                <div className="space-y-4">
                  {files.map((file, idx) => {
                    const pKey = `${face}-${idx}`
                    const result = faceResults[idx]
                    const isProc = processing[pKey]

                    return (
                      <div key={idx} className="bg-slate-900/40 rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs text-slate-400 font-mono">#{idx + 1}</span>
                          <span className="text-xs text-slate-500 truncate max-w-[200px]">{file.name}</span>
                          {isProc && <StatusBadge status="loading" label="처리 중..." />}
                          {result && !result.error && <StatusBadge status="success" label={result.method === 'ai' ? 'AI' : 'OpenCV'} />}
                          {result?.error && <StatusBadge status="error" label="실패" />}
                          {!result && !isProc && (
                            <button
                              onClick={() => processOne(face, file, idx)}
                              className="text-xs text-blue-400 hover:text-blue-300 ml-auto"
                            >
                              개별 실행
                            </button>
                          )}
                        </div>
                        <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-8 gap-2">
                          <ImagePreview
                            src={URL.createObjectURL(file)}
                            label="원본"
                            className="aspect-square"
                          />
                          {result?.outputs && Object.entries(result.outputs).map(([k, url]) => (
                            <ImagePreview
                              key={k}
                              src={url}
                              label={RESULT_LABELS[k] || k}
                              className="aspect-square"
                            />
                          ))}
                        </div>
                        {/* 메타데이터 */}
                        {result && !result.error && (
                          <div className="flex gap-4 mt-2 text-xs text-slate-500">
                            {result.quad_found && <span className="text-emerald-400">4꼭짓점 검출 성공</span>}
                            {result.quad_found === false && <span className="text-amber-400">4꼭짓점 미검출 (fallback)</span>}
                            {result.line_count != null && <span>직선 {result.line_count}개</span>}
                            <span>{result.method === 'ai' ? 'AI 배경분리' : 'OpenCV'}</span>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
