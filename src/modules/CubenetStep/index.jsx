/**
 * 모듈: 주사위 전개도 구성 (v2)
 * 전처리/파노라마 결과를 자동으로 사용
 * 전면(front) 기준 기울기/비율 정규화 적용
 * 다른 모듈과의 의존성: 없음 (props로 데이터 수신)
 */
import { useState } from 'react'
import { Box, Play, Info } from 'lucide-react'
import { FACES, FACE_LABELS } from '../../utils/constants'
import { cubenetAPI } from '../../utils/api'
import ImagePreview from '../../components/ImagePreview'
import StatusBadge from '../../components/StatusBadge'

const SOURCE_LABELS = {
  panorama: '파노라마',
  warped: '정면 보정',
  separated: '배경 분리',
  corrected: '보정',
  cropped: '크롭',
  original: '원본',
  none: '없음',
}

const SOURCE_COLORS = {
  panorama: 'text-emerald-400',
  warped: 'text-cyan-400',
  separated: 'text-blue-400',
  corrected: 'text-cyan-400',
  cropped: 'text-amber-400',
  original: 'text-slate-400',
  none: 'text-red-400',
}

export default function CubenetStep({ uploadedFiles, panoramas, preprocessed, result, onResult }) {
  const [processing, setProcessing] = useState(false)

  // 각 면에 사용될 소스 판단 (전처리 결과 우선)
  const getFaceSource = (face) => {
    const pp = preprocessed[face]
    if (Array.isArray(pp)) {
      const last = pp[pp.length - 1]
      if (last?.outputs?.warped) return 'warped'
      if (last?.outputs?.separated) return 'separated'
    }
    if (uploadedFiles[face]?.length > 0) return 'original'
    return 'none'
  }

  // 전처리 결과를 자동 탐색하여 전개도 생성 (적응형)
  const buildNetAuto = async () => {
    setProcessing(true)
    try {
      const res = await cubenetAPI.buildAuto()
      onResult(res.data)
    } catch (err) {
      console.error('전개도 생성 실패:', err)
      onResult({ error: err.response?.data?.detail || err.message })
    } finally {
      setProcessing(false)
    }
  }

  const availableFaces = FACES.filter(f => getFaceSource(f) !== 'none')
  const hasPreprocessed = FACES.some(f => {
    const src = getFaceSource(f)
    return src !== 'none' && src !== 'original'
  })

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-medium text-slate-200 mb-1">주사위 전개도 구성</h2>
          <p className="text-sm text-slate-400">
            전처리된 이미지를 기반으로 전개도를 구성합니다.
            전면(front) 기준으로 기울기/비율이 정규화됩니다.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={buildNetAuto}
            disabled={processing || availableFaces.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg text-sm font-medium transition-colors"
          >
            <Box size={14} />
            전개도 생성
          </button>
        </div>
      </div>

      {/* 안내 메시지 */}
      {!hasPreprocessed && availableFaces.length > 0 && (
        <div className="flex items-start gap-2 mb-4 p-3 bg-amber-900/20 border border-amber-700/30 rounded-lg">
          <Info size={16} className="text-amber-400 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-amber-300">
            전처리되지 않은 원본 이미지가 사용됩니다. 더 나은 결과를 위해 먼저 전처리 단계를 실행하세요.
          </p>
        </div>
      )}

      {/* 면별 소스 상태 */}
      <div className="grid grid-cols-5 gap-3 mb-6">
        {FACES.map(face => {
          const source = getFaceSource(face)
          const isFront = face === 'front'
          return (
            <div
              key={face}
              className={`p-3 rounded-lg border text-center ${
                source !== 'none'
                  ? isFront
                    ? 'border-blue-500/50 bg-blue-950/30'
                    : 'border-slate-600 bg-slate-800/50'
                  : 'border-slate-700/30 bg-slate-800/20'
              }`}
            >
              <p className="text-sm font-medium text-slate-300 mb-1">
                {FACE_LABELS[face]}
                {isFront && <span className="text-blue-400 text-xs ml-1">(기준)</span>}
              </p>
              <span className={`text-xs ${SOURCE_COLORS[source]}`}>
                {SOURCE_LABELS[source]}
              </span>
            </div>
          )
        })}
      </div>

      {/* 전개도 시각화 미리보기 */}
      <div className="mb-6">
        <p className="text-xs text-slate-500 mb-2">전개도 레이아웃 미리보기</p>
        <div className="inline-grid" style={{ gridTemplateColumns: 'repeat(4, 80px)', gridTemplateRows: 'repeat(3, 80px)', gap: 0 }}>
          {/* Row 0: _, front(기준), _, _ */}
          <div />
          <FaceTile face="front" source={getFaceSource('front')} preprocessed={preprocessed} panoramas={panoramas} uploadedFiles={uploadedFiles} isFront />
          <div />
          <div />
          {/* Row 1: left, 밑면X, right, back */}
          <FaceTile face="left" source={getFaceSource('left')} preprocessed={preprocessed} panoramas={panoramas} uploadedFiles={uploadedFiles} />
          <BottomTile />
          <FaceTile face="right" source={getFaceSource('right')} preprocessed={preprocessed} panoramas={panoramas} uploadedFiles={uploadedFiles} />
          <FaceTile face="back" source={getFaceSource('back')} preprocessed={preprocessed} panoramas={panoramas} uploadedFiles={uploadedFiles} />
          {/* Row 2: _, top, _, _ */}
          <div />
          <FaceTile face="top" source={getFaceSource('top')} preprocessed={preprocessed} panoramas={panoramas} uploadedFiles={uploadedFiles} />
          <div />
          <div />
        </div>
      </div>

      {/* 전개도 결과 */}
      {processing && <StatusBadge status="loading" label="생성 중..." />}
      {result && !result.error && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <StatusBadge status="success" label={`${result.faces_used?.length || 0}면 사용`} />
            {result.front_size && (
              <span className="text-xs text-blue-400">
                기준(전면): {result.front_size[0]}×{result.front_size[1]}px
              </span>
            )}
            {result.missing_faces?.length > 0 && (
              <span className="text-xs text-amber-400">
                누락: {result.missing_faces.map(f => FACE_LABELS[f]).join(', ')}
              </span>
            )}
            {result.sources && (
              <span className="text-xs text-slate-500">
                {Object.entries(result.sources).map(([f, s]) =>
                  `${FACE_LABELS[f]}(${SOURCE_LABELS[s]})`
                ).join(', ')}
              </span>
            )}
          </div>
          <ImagePreview
            src={result.net_url}
            label="주사위 전개도"
            className="max-w-2xl aspect-auto"
          />
        </div>
      )}
      {result?.error && (
        <div className="p-3 bg-red-900/20 border border-red-700/30 rounded-lg text-sm text-red-300">
          {result.error}
        </div>
      )}
    </div>
  )
}

// 전개도 미리보기 타일 - warped 우선 표시
function FaceTile({ face, source, preprocessed, panoramas, uploadedFiles, isFront }) {
  let imgSrc = null

  if (Array.isArray(preprocessed?.[face])) {
    const last = preprocessed[face][preprocessed[face].length - 1]
    if (last?.outputs?.warped) imgSrc = last.outputs.warped
    else if (last?.outputs?.separated) imgSrc = last.outputs.separated
  }
  if (!imgSrc && uploadedFiles[face]?.length > 0) {
    imgSrc = URL.createObjectURL(uploadedFiles[face][0])
  }

  return (
    <div className={`w-20 h-20 rounded border flex items-center justify-center text-xs overflow-hidden ${
      imgSrc
        ? isFront ? 'border-blue-500/70 bg-slate-800' : 'border-blue-500/30 bg-slate-800'
        : 'border-slate-700/30 bg-slate-800/20 text-slate-600'
    }`}>
      {imgSrc ? (
        <img src={imgSrc} alt={face} className="w-full h-full object-cover" />
      ) : (
        FACE_LABELS[face]
      )}
    </div>
  )
}

// 밑면 타일 (사용 안 함)
function BottomTile() {
  return (
    <div className="w-20 h-20 rounded border border-red-500/30 bg-red-950/20 flex flex-col items-center justify-center text-xs text-red-400/70">
      <span className="text-lg font-bold leading-none">X</span>
      <span className="mt-0.5">밑면</span>
    </div>
  )
}
