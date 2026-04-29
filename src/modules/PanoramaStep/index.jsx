/**
 * 모듈: 파노라마 합성
 * 같은 면에서 촬영한 여러 장의 이미지를 합성
 * 다른 모듈과의 의존성: 없음 (props로 데이터 수신)
 */
import { useState } from 'react'
import { Play, Layers } from 'lucide-react'
import { FACES, FACE_LABELS } from '../../utils/constants'
import { panoramaAPI } from '../../utils/api'
import ImagePreview from '../../components/ImagePreview'
import StatusBadge from '../../components/StatusBadge'

export default function PanoramaStep({ uploadedFiles, preprocessed, results, onResult }) {
  const [processing, setProcessing] = useState({})
  const [method, setMethod] = useState('orb')

  // 원본 이미지로 합성
  const stitchFace = async (face) => {
    const files = uploadedFiles[face]
    if (!files || files.length < 2) return

    setProcessing(prev => ({ ...prev, [face]: true }))
    try {
      const res = await panoramaAPI.stitch(files, face, method)
      onResult(face, res.data)
    } catch (err) {
      console.error(`파노라마 실패 (${face}):`, err)
      onResult(face, { error: err.message })
    } finally {
      setProcessing(prev => ({ ...prev, [face]: false }))
    }
  }

  // 전처리(보정) 이미지로 합성
  const stitchPreprocessed = async (face) => {
    setProcessing(prev => ({ ...prev, [face]: true }))
    try {
      const res = await panoramaAPI.stitchPreprocessed(face, method)
      onResult(face, res.data)
    } catch (err) {
      console.error(`전처리 기반 파노라마 실패 (${face}):`, err)
      onResult(face, { error: err.message })
    } finally {
      setProcessing(prev => ({ ...prev, [face]: false }))
    }
  }

  const stitchAll = async () => {
    for (const face of FACES) {
      const hasPreprocessed = Array.isArray(preprocessed?.[face]) && preprocessed[face].length >= 2
      if (hasPreprocessed) {
        await stitchPreprocessed(face)
      } else if ((uploadedFiles[face]?.length || 0) >= 2) {
        await stitchFace(face)
      }
    }
  }

  const facesMultiple = FACES.filter(f => (uploadedFiles[f]?.length || 0) >= 2)
  const facesSingle = FACES.filter(f => (uploadedFiles[f]?.length || 0) === 1)

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-medium text-slate-200 mb-1">파노라마 합성</h2>
          <p className="text-sm text-slate-400">
            같은 면에서 촬영한 여러 장의 사진을 이어 붙여 한 장으로 합성합니다.
            {facesSingle.length > 0 && (
              <span className="text-slate-500">
                {' '}({facesSingle.map(f => FACE_LABELS[f]).join(', ')}은 1장이라 합성 불필요)
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-400">
            <span>방식</span>
            <select
              value={method}
              onChange={e => setMethod(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-slate-300"
            >
              <option value="orb">ORB (빠름)</option>
              <option value="sift">SIFT (정밀)</option>
            </select>
          </label>
          <button
            onClick={stitchAll}
            disabled={facesMultiple.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg text-sm font-medium transition-colors"
          >
            <Layers size={14} />
            전체 합성
          </button>
        </div>
      </div>

      {facesMultiple.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          {Object.keys(uploadedFiles).length === 0
            ? '먼저 이미지를 업로드하세요'
            : '한 면에 2장 이상 업로드된 면이 없습니다 (1장이면 합성 불필요)'
          }
        </div>
      ) : (
        <div className="space-y-6">
          {facesMultiple.map(face => {
            const files = uploadedFiles[face] || []
            const result = results[face]
            const isProcessing = processing[face]

            return (
              <div key={face} className="bg-slate-800/40 rounded-xl p-4 border border-slate-700/50">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-300">{FACE_LABELS[face]}</span>
                    <span className="text-xs text-slate-500">{files.length}장 → 1장</span>
                    {isProcessing && <StatusBadge status="loading" label="합성 중..." />}
                    {result && !result.error && <StatusBadge status="success" label={`매칭 ${result.match_counts?.join(', ') || '-'}점`} />}
                    {result?.error && <StatusBadge status="error" label="실패" />}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => stitchFace(face)}
                      disabled={isProcessing}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs bg-slate-700 hover:bg-slate-600 disabled:opacity-50 rounded-lg transition-colors"
                    >
                      <Play size={12} />
                      원본 합성
                    </button>
                    {Array.isArray(preprocessed?.[face]) && preprocessed[face].length >= 2 && (
                      <button
                        onClick={() => stitchPreprocessed(face)}
                        disabled={isProcessing}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs bg-blue-700 hover:bg-blue-600 disabled:opacity-50 rounded-lg transition-colors"
                      >
                        <Play size={12} />
                        보정 합성
                      </button>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {/* 입력 이미지들 */}
                  <div>
                    <p className="text-xs text-slate-500 mb-2">입력 ({files.length}장)</p>
                    <div className="grid grid-cols-2 gap-2">
                      {files.map((file, idx) => (
                        <ImagePreview
                          key={idx}
                          src={URL.createObjectURL(file)}
                          label={`${idx + 1}번`}
                          className="aspect-video"
                        />
                      ))}
                    </div>
                  </div>

                  {/* 합성 결과 */}
                  <div>
                    <p className="text-xs text-slate-500 mb-2">합성 결과</p>
                    {result?.panorama_url ? (
                      <ImagePreview
                        src={result.panorama_url}
                        label="파노라마"
                        className="aspect-video"
                      />
                    ) : (
                      <div className="aspect-video bg-slate-800/60 rounded-lg border border-slate-700/30 flex items-center justify-center text-xs text-slate-600">
                        대기 중
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
