/**
 * 메인 대시보드 앱
 * 각 모듈 컴포넌트를 조합하고 파이프라인 상태를 관리
 * 모듈 간 직접 의존은 없으며, 데이터는 usePipeline 훅을 통해 전달
 */
import { useState, useEffect } from 'react'
import { Box, Wifi, WifiOff, RotateCcw } from 'lucide-react'
import { healthCheck, resetAll } from './utils/api'
import usePipeline from './hooks/usePipeline'
import StepNav from './components/StepNav'

// ── 모듈 컴포넌트 (각각 독립적) ──
import DroneControlStep from './modules/DroneControlStep' // 1. 신규 추가
import UploadStep from './modules/UploadStep'
import PreprocessStep from './modules/PreprocessStep'
import PanoramaStep from './modules/PanoramaStep'
import CubenetStep from './modules/CubenetStep'
import ViewerStep from './modules/ViewerStep'

export default function App() {
  const {
    state,
    setActiveStep,
    setUploadedFiles,
    setPreprocessResult,
    setPanoramaResult,
    setCubenetResult,
    reset,
  } = usePipeline()

  const [serverOnline, setServerOnline] = useState(null)

  // 서버 상태 확인
  useEffect(() => {
    const check = async () => {
      try {
        await healthCheck()
        setServerOnline(true)
      } catch {
        setServerOnline(false)
      }
    }
    check()
    const interval = setInterval(check, 30000)
    return () => clearInterval(interval)
  }, [])

  // 완료된 단계 계산
  const completedSteps = []
  if (Object.keys(state.uploadedFiles).length > 0) completedSteps.push('upload')
  if (Object.keys(state.preprocessed).length > 0) completedSteps.push('preprocess')
  if (Object.keys(state.panoramas).length > 0) completedSteps.push('panorama')
  if (state.cubenet) completedSteps.push('cubenet')

  // 현재 활성 단계에 맞는 컴포넌트 렌더링
  const renderStep = () => {
    switch (state.activeStep) {
      case 'control': // 2. 신규 케이스 추가
        return <DroneControlStep />
      case 'upload':
        return (
          <UploadStep
            uploadedFiles={state.uploadedFiles}
            onFilesChange={setUploadedFiles}
          />
        )
      case 'preprocess':
        return (
          <PreprocessStep
            uploadedFiles={state.uploadedFiles}
            results={state.preprocessed}
            onResult={setPreprocessResult}
          />
        )
      case 'panorama':
        return (
          <PanoramaStep
            uploadedFiles={state.uploadedFiles}
            preprocessed={state.preprocessed}
            results={state.panoramas}
            onResult={setPanoramaResult}
          />
        )
      case 'cubenet':
        return (
          <CubenetStep
            uploadedFiles={state.uploadedFiles}
            panoramas={state.panoramas}
            preprocessed={state.preprocessed}
            result={state.cubenet}
            onResult={setCubenetResult}
          />
        )
      case 'viewer':
        return <ViewerStep />
      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200">
      {/* 헤더 */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
            <Box size={18} className="text-blue-400" />
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-tight">3D 모델링 파이프라인</h1>
            <p className="text-xs text-slate-500">드론 활용 사물 3D 모델링 · 3팀 화력발전소</p>
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <button
            onClick={async () => {
              if (confirm('모든 처리 결과를 초기화하시겠습니까?')) {
                try { await resetAll() } catch {}
                reset()
              }
            }}
            className="flex items-center gap-1 px-2.5 py-1.5 text-slate-400 hover:text-red-400 bg-slate-800/60 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <RotateCcw size={12} />
            초기화
          </button>
          {serverOnline === true && (
            <span className="flex items-center gap-1 text-emerald-400">
              <Wifi size={12} /> 서버 연결됨
            </span>
          )}
          {serverOnline === false && (
            <span className="flex items-center gap-1 text-red-400">
              <WifiOff size={12} /> 서버 오프라인
            </span>
          )}
          {serverOnline === null && (
            <span className="text-slate-500">연결 확인 중...</span>
          )}
        </div>
      </header>

      {/* 단계 네비게이션 */}
      <StepNav
        activeStep={state.activeStep}
        onStepClick={setActiveStep}
        completedSteps={completedSteps}
      />

      {/* 메인 콘텐츠 */}
      <main className="max-w-7xl mx-auto">
        {renderStep()}
      </main>
    </div>
  )
}
